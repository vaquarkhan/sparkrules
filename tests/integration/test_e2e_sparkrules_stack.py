"""End-to-end journeys: HTTP surface + KIE + metadata store + DMN + compliance + policy stubs.

These tests complement unit coverage by wiring multiple subsystems in one process.
They do **not** replace roadmap items in ``FUTURE_WORK.md`` (full Rete, full KIE parity, etc.).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from sparkrules.api import AppDeps, create_app
from sparkrules.api.kie import reset_kie_containers_for_tests
from sparkrules.compliance import (
    AdverseActionContext,
    Jurisdiction,
    adverse_action_counterfactual_summary,
    build_adverse_action_notice,
)
from sparkrules.dmn import counterfactual_dmn_decision_table_xml, parse_dmn_decision_table_xml
from sparkrules.integrations.feast_client import (
    FeastFeatureClient,
    feast_fetch_row,
    merge_features_into_fact,
)
from sparkrules.model.rule import Rule, RuleDefinition, RuleFormat, new_rule_id
from sparkrules.policy.ranger_client import query_ranger_allowed
from sparkrules.policy.ranger_compat import ranger_allow_stub
from sparkrules.store.backends import create_rule_store

pytestmark = pytest.mark.integration

_DRL = """
rule e2e when $t : T ( true ) then
result.ok = true;
result.decision = "approve";
end
"""

_MINI_DMN = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn" id="e2eDmn">
  <decision id="d1" name="E2EDecision">
    <decisionTable id="tbl">
      <input id="i1">
        <inputExpression typeRef="string"><text>$.k</text></inputExpression>
      </input>
      <output id="o1" name="out" />
      <rule id="r1">
        <inputEntry><text>-</text></inputEntry>
        <outputEntry><text>"ok"</text></outputEntry>
      </rule>
    </decisionTable>
  </decision>
</definitions>
"""


def test_e2e_health_and_rule_publish() -> None:
    c = TestClient(create_app(AppDeps()))
    h = c.get("/health")
    assert h.status_code == 200
    r = c.post(
        "/rules",
        json={"rule_handle": "e2e_stack_rule", "group": "e2e", "drl": _DRL},
    )
    assert r.status_code == 200


def test_e2e_kie_deploy_execute_delete() -> None:
    reset_kie_containers_for_tests()
    c = TestClient(create_app(AppDeps()))
    assert (
        c.put(
            "/kie-server/services/rest/server/containers/e2e-stack",
            json={"drl": _DRL},
        ).status_code
        == 200
    )

    exe = c.post(
        "/kie-server/services/rest/server/containers/instances/e2e-stack",
        json={
            "commands": [
                {"insert": {"object": {"com.demo.T": {"v": 1}}}},
                {"fire-all-rules": {}},
            ],
        },
    )
    assert exe.status_code == 200
    inner = json.loads(exe.json()["result"])
    assert inner["final-action"].get("decision") == "approve"
    assert any(s.get("fired") for s in inner["results"])

    assert c.delete("/kie-server/services/rest/server/containers/e2e-stack").status_code == 200
    assert c.get("/kie-server/services/rest/server/containers/e2e-stack").status_code == 404


def test_e2e_supporting_domain_modules() -> None:
    c = TestClient(create_app(AppDeps()))
    dt = parse_dmn_decision_table_xml(_MINI_DMN)
    assert dt.name == "E2EDecision" and len(dt.rows) == 1

    ev = c.post("/dmn/evaluate", json={"xml": _MINI_DMN, "env": {"k": "z"}})
    assert ev.status_code == 200 and ev.json()["result"] == {"out": "ok"}
    cf_http = c.post(
        "/dmn/counterfactual",
        json={"xml": _MINI_DMN, "base_env": {"k": "1"}, "env_patch": {"k": "2"}},
    )
    assert cf_http.status_code == 200 and cf_http.json()["outputs_differ"] is False

    cf = counterfactual_dmn_decision_table_xml(_MINI_DMN, {"k": "x"}, {"k": "y"})
    assert cf["outputs_differ"] is False and cf["base"] == cf["counterfactual"] == {"out": "ok"}

    base_aa = AdverseActionContext(
        "acct-e2e", "2026-05-01", ("R1",), creditor_or_controller_name="Bank"
    )
    txt = build_adverse_action_notice(base_aa, Jurisdiction.US_ECOA_FCRA)
    assert "ECOA" in txt
    alt_aa = AdverseActionContext(
        "acct-e2e", "2026-05-01", ("R1", "R2"), creditor_or_controller_name="Bank"
    )
    csum = adverse_action_counterfactual_summary(base_aa, alt_aa, Jurisdiction.US_ECOA_FCRA)
    assert csum["reason_codes_added"] == ["R2"] and csum["notices_differ"] is True

    assert (
        ranger_allow_stub(user="alice", resource_type="tbl", resource_name="t", action="select")
        is True
    )

    sink_calls: list[tuple[str, int]] = []

    def sink(_blob: str, handle: str, ver: int) -> None:
        sink_calls.append((handle, ver))

    store = create_rule_store("iceberg", iceberg_version_sink=sink)
    t0 = datetime(2026, 5, 1, tzinfo=UTC)
    rule = Rule(
        rule_id=new_rule_id(),
        rule_handle="e2e-ice",
        version=99,
        rule_group="g",
        salience=0,
        effective_from=t0,
        effective_to=None,
        is_active=True,
        rule_definition=RuleDefinition("r", RuleFormat.DRL),
        activation_group=None,
    )
    store.insert(rule)
    assert sink_calls and sink_calls[0][0] == "e2e-ice"


def test_e2e_feast_merge_and_ranger_http() -> None:
    ms = MagicMock()

    class _Fv:
        def to_dict(self) -> dict[str, list[float]]:
            return {"f_score": [0.42]}

    ms.get_online_features.return_value = _Fv()
    cli = FeastFeatureClient(repo_path="/tmp/e2e", _store=ms)
    row = feast_fetch_row(cli, features=["f:v1"], entity_id_field="id", entity_id="99")
    assert row["f_score"] == 0.42
    fact: dict[str, object] = {"x": 1}
    merge_features_into_fact(fact, {"a-b": 2})
    assert fact["feat_a_b"] == 2

    ok = MagicMock(status_code=200, text="{}")
    ok.json.return_value = {"isAllowed": True}
    with patch.object(httpx, "post", return_value=ok):
        assert query_ranger_allowed(
            "http://policy-gw/",
            user="u",
            resource_type="dataset",
            resource_name="d",
            action="read",
            evaluate_path="/allow",
        )

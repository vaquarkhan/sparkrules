import pytest
from fastapi.testclient import TestClient

from sparkrules.api import AppDeps, create_app
from sparkrules.runtime import EngineConfig


def test_health() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_simulation() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations",
        json={
            "drl": """
rule r1
when
$t : T ( $t.x == 1 )
then
result.ok = true;
end
""",
            "fact": {"t": {"x": 1}},
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["fired"] is True


def test_simulation_chain() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/chain",
        json={
            "drl": """
rule a
stop_on_fire true
when $t : T ( true ) then
result.n = 1;
end
rule b
when $t : T ( true ) then
result.m = 2;
end
""",
            "fact": {"t": {}},
            "stop_on_decline": False,
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["any_fired"] is True
    assert j["stop_reason"] and j["stop_reason"].startswith("stop_on_fire:")
    assert len(j["steps"]) == 1


def test_simulation_chain_bad_drl_422() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/chain",
        json={"drl": "not valid", "fact": {}},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "DRL_PARSE_ERROR"


def test_simulation_unbound_path_returns_structured_400() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations",
        json={
            "drl": """
rule r
when
$t : T ( $t.amount >= 100 )
then
result.ok = true;
end
""",
            "fact": {"amount": 5000},
        },
    )
    assert r.status_code == 400
    j = r.json()
    assert j["error"]["code"] == "UNBOUND_OR_NULL"
    assert "amount" in j["error"]["message"] or "t" in j["error"]["message"]


def test_simulation_chain_agenda_group_mode() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/chain",
        json={
            "drl": """
rule a salience 10
agenda_group "auth"
when $t : T ( true ) then
result.step = "a";
end
rule b salience 0
agenda_group "auth"
when $t : T ( true ) then
result.step = "b";
end
""",
            "fact": {"t": {}},
            "agenda_group_modes": {"auth": "first_match"},
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["steps"][0]["fired"] is True
    assert j["steps"][1]["skipped"] is True


def test_simulation_chain_uses_engine_policy_default() -> None:
    app = create_app(AppDeps(engine_cfg=EngineConfig(stop_on_decline=True)))
    c = TestClient(app)
    r = c.post(
        "/simulations/chain",
        json={
            "drl": """
rule decline
when $t : T ( true ) then
result.decision = "decline";
end
rule later
when $t : T ( true ) then
result.x = 1;
end
""",
            "fact": {"t": {}},
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["stop_reason"] == "stop_on_decline"


def test_simulation_shadow() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/shadow",
        json={
            "primary_drl": 'rule a when $t : T ( true ) then result.decision = "approve"; end',
            "shadow_drl": 'rule b when $t : T ( true ) then result.decision = "decline"; end',
            "fact": {"t": {}},
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["drifted"] is True
    assert j["drift_fields"] == ["decision"]


def test_simulation_coverage() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/coverage",
        json={
            "drl": """
rule a
when $t : T ( $t.x == 1 ) then
result.ok = true;
end
rule b
when $t : T ( $t.y > 10 ) then
result.ok2 = true;
end
""",
            "facts": [{"t": {"x": 1, "y": 0}}, {"t": {"x": 0, "y": 11}}],
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["total_facts"] == 2
    assert j["total_rules"] == 2
    assert j["covered_rules"] == 2


def test_simulation_coverage_bad_drl_422() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/coverage",
        json={"drl": "not drl", "facts": []},
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 422


def test_lsp_analyze_endpoint() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    h = {"X-Roles": "rule_reader", "X-Tenant-Id": "default"}
    ok = c.post(
        "/ide/lsp/analyze",
        json={"drl": "rule r when $t : T ( true ) then result.ok = true; end", "prefix": "ru"},
        headers=h,
    )
    assert ok.status_code == 200
    j = ok.json()
    assert j["diagnostics"] == []
    assert "rule" in j["completions"]
    bad = c.post(
        "/ide/lsp/analyze",
        json={"drl": "bad drl", "prefix": ""},
        headers=h,
    )
    assert bad.status_code == 200
    assert bad.json()["diagnostics"]
    bad_tok = c.post(
        "/ide/lsp/analyze",
        json={
            "drl": "rule a\nwhen\n$t : T ( $t.x == @ ) then end",
            "prefix": "",
        },
        headers=h,
    )
    assert bad_tok.status_code == 200
    d0 = bad_tok.json()["diagnostics"][0]
    assert d0["line"] == 3 and d0["col"] >= 10


def test_simulation_counterfactual() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/counterfactual",
        json={
            "drl": 'rule r when $t : T ( $t.x > 10 ) then result.decision = "decline"; end',
            "baseline_fact": {"t": {"x": 5}},
            "candidate_fact": {"t": {"x": 20}},
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["drifted"] is True
    assert "decision" in j["drift_fields"]


_MINI_DMN_API = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn" id="apiDmn">
  <decision id="d1" name="ApiDecision">
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


def test_dmn_evaluate_http_ok() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/dmn/evaluate",
        json={"xml": _MINI_DMN_API, "env": {"k": "x"}},
    )
    assert r.status_code == 200
    assert r.json()["result"] == {"out": "ok"}


def test_dmn_evaluate_bad_xml_422() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post("/dmn/evaluate", json={"xml": "<<<", "env": {}})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "DMN_PARSE_ERROR"


def test_dmn_evaluate_collect_aggregate_numeric_error_400() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="COLLECT SUM">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="o"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>1</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"x"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post("/dmn/evaluate", json={"xml": xml, "env": {"k": "1"}})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "DMN_AGGREGATE_ERROR"


def test_dmn_evaluate_collect_aggregate_multi_output_ok() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="COLLECT SUM">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="a"/><output name="b"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>1</text></outputEntry><outputEntry><text>2</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>10</text></outputEntry><outputEntry><text>20</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post("/dmn/evaluate", json={"xml": xml, "env": {"k": "1"}})
    assert r.status_code == 200
    assert r.json()["result"] == {"a": 11, "b": 22}


def test_dmn_evaluate_unique_overlap_400() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="UNIQUE">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="o"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>1</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>2</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post("/dmn/evaluate", json={"xml": xml, "env": {"k": "z"}})
    assert r.status_code == 400
    body = r.json()["detail"]
    assert body["code"] == "DMN_UNIQUE_OVERLAP"


def test_dmn_counterfactual_http_ok() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/dmn/counterfactual",
        json={"xml": _MINI_DMN_API, "base_env": {"k": "a"}, "env_patch": {"k": "b"}},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["outputs_differ"] is False and j["base"] == j["counterfactual"]


def test_dmn_counterfactual_bad_xml_422() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/dmn/counterfactual",
        json={"xml": "<<<", "base_env": {}, "env_patch": {}},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "DMN_PARSE_ERROR"


def test_dmn_counterfactual_unique_overlap_400() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="UNIQUE">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="o"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>1</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>2</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/dmn/counterfactual",
        json={"xml": xml, "base_env": {"k": "z"}, "env_patch": {}},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "DMN_UNIQUE_OVERLAP"


def test_dmn_counterfactual_collect_aggregate_numeric_error_400() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="COLLECT SUM">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="o"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>1</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"x"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/dmn/counterfactual",
        json={"xml": xml, "base_env": {"k": "1"}, "env_patch": {}},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "DMN_AGGREGATE_ERROR"


def test_dmn_evaluate_unexpected_error_400(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a: object, **_k: object) -> object:
        raise ValueError("forced")

    monkeypatch.setattr("sparkrules.api.app.evaluate_dmn_decision_table_xml", _boom)
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post("/dmn/evaluate", json={"xml": _MINI_DMN_API, "env": {}})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "DMN_EVALUATE_FAILED"


def test_dmn_counterfactual_unexpected_error_400(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a: object, **_k: object) -> object:
        raise RuntimeError("forced")

    monkeypatch.setattr("sparkrules.api.app.counterfactual_dmn_decision_table_xml", _boom)
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/dmn/counterfactual",
        json={"xml": _MINI_DMN_API, "base_env": {}, "env_patch": {}},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "DMN_COUNTERFACTUAL_FAILED"


def test_simulation_counterfactual_bad_drl_422() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/counterfactual",
        json={
            "drl": "bad drl",
            "baseline_fact": {"t": {"x": 1}},
            "candidate_fact": {"t": {"x": 2}},
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 422


def test_time_travel_capture_and_replay() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    h = {"X-Roles": "run_operator", "X-Tenant-Id": "default"}
    cap = c.post(
        "/debug/time-travel/capture",
        json={
            "run_id": "dbg-1",
            "drl": "rule r when $t : T ( true ) then result.ok = true; end",
            "fact": {"t": {"x": 1}},
        },
        headers=h,
    )
    assert cap.status_code == 200
    cj = cap.json()
    rep = c.post(
        "/debug/time-travel/replay",
        json={"snapshot_id": cj["snapshot_id"], "run_id": "dbg-1"},
        headers=h,
    )
    assert rep.status_code == 200
    assert rep.json()["fired"] is True


def test_time_travel_capture_bad_drl_422() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    h = {"X-Roles": "run_operator", "X-Tenant-Id": "default"}
    cap = c.post(
        "/debug/time-travel/capture",
        json={
            "run_id": "dbg-bad",
            "drl": "bad drl",
            "fact": {"t": {"x": 1}},
        },
        headers=h,
    )
    assert cap.status_code == 422


def test_time_travel_replay_error_paths() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    h = {"X-Roles": "run_operator", "X-Tenant-Id": "default"}
    missing = c.post(
        "/debug/time-travel/replay",
        json={"snapshot_id": 0, "run_id": "nope"},
        headers=h,
    )
    assert missing.status_code == 404
    cap = c.post(
        "/debug/time-travel/capture",
        json={
            "run_id": "dbg-2",
            "drl": "rule r when $t : T ( $t.x > 0 ) then result.ok = true; end",
            "fact": {"t": {"x": 1}},
        },
        headers=h,
    )
    sid = cap.json()["snapshot_id"]
    bad = c.post(
        "/debug/time-travel/replay",
        json={"snapshot_id": sid, "run_id": "dbg-2", "fact_override": {}},
        headers=h,
    )
    assert bad.status_code == 400

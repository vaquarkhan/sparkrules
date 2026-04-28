"""Targeted tests for branches previously below full sre coverage."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from sre.ai import AiService, StubAiProvider
from sre.api import AppDeps, create_app
from sre.compiler import RuleEvaluationError, evaluate_rule
from sre.ide import lsp as lsp_mod
from sre.parser import parse
from sre.parser.ast import ParseError
from sre.runtime.two_pass import TwoPassOrchestrator


def test_line_col_default_when_no_location_suffix() -> None:
    assert lsp_mod._line_col_from_message("no line here") == (1, 1)


def test_two_pass_group_path_hits_non_mapping() -> None:
    p1 = "rule p1 when $t : T ( true ) then end"
    p2 = "rule p2 when $t : T ( true ) then end"
    orch = TwoPassOrchestrator(p1, p2, group_by=("t.a",))
    r = orch.run([{"t": 1}])
    assert r.aggregates


def test_contains_branch_none_operand_short_circuits() -> None:
    drl = """
rule r
when
$t : T ( [1, 2, 3] contains $t.x )
then
end
"""
    rule = parse(drl)
    m = evaluate_rule(rule, {"t": {}})
    assert m.fired is False


def test_compare_incompatible_types_raises_rule_evaluation_error() -> None:
    drl = """
rule r
when
$t : T ( $t.a > $t.b )
then
end
"""
    rule = parse(drl)
    with pytest.raises(RuleEvaluationError) as ei:
        evaluate_rule(rule, {"t": {"a": "x", "b": 1}})
    assert ei.value.code == "COMPARISON_TYPE_ERROR"


def test_local_default_roles_grants_configured_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SPARKRULES_DEV_ALLOW_DEFAULT_SUPERUSER", raising=False)
    monkeypatch.setenv("SPARKRULES_LOCAL_DEFAULT_ROLES", "rule_reader")
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.get("/rules/assets")
    assert r.status_code == 200


def test_stub_explain_non_parse_error_from_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sre.ai.service import _stub_explain_from_drl

    def boom(_s: str) -> object:
        raise RuntimeError("parse blew up")

    monkeypatch.setattr("sre.parser.parse", boom)
    out = _stub_explain_from_drl({"drl": "anything"})
    assert "unexpected error" in out.lower() or "RuntimeError" in out


def test_record_simulation_rejects_when_not_pending() -> None:
    svc = AiService(StubAiProvider())
    suggestions = svc.create_rule_suggestions(
        namespace="default",
        payload={"rule_handle": "h", "facts": []},
        principal="x",
    )
    sid = suggestions[0].id
    cur = svc.store.get(sid)
    svc.store.upsert(replace(cur, status="APPROVED"))
    with pytest.raises(ValueError, match="only PENDING"):
        svc.record_simulation_evidence(sid, fired=False, action={}, bound={})


def test_get_rule_version_404_unknown() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.get(
        "/rules/definitely_missing_handle_here/version/1",
        headers={"X-Roles": "rule_reader", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 404


def _client_with_boom_run() -> TestClient:
    deps = AppDeps()

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("simulated failure")

    deps.sim.run = boom  # type: ignore[assignment]
    return TestClient(create_app(deps))


def test_post_simulations_generic_exception_is_400() -> None:
    c = _client_with_boom_run()
    r = c.post(
        "/simulations",
        json={"drl": "rule r when $t : T ( true ) then end", "fact": {"t": {}}},
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "SIMULATION_FAILED"


def test_post_simulations_shadow_rule_evaluation_error_lineage() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/shadow",
        json={
            "primary_drl": "rule p when $t : T ( $t.x > 1 ) then result.a = 1; end",
            "shadow_drl": "rule s when $t : T ( true ) then result.b = 1; end",
            "fact": {},
            "run_id": "shadow-rev-test",
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 400


def test_post_simulations_shadow_generic_exception_lineage() -> None:
    deps = AppDeps()

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("shadow boom")

    deps.sim.run_shadow = boom  # type: ignore[assignment]
    c = TestClient(create_app(deps))
    r = c.post(
        "/simulations/shadow",
        json={
            "primary_drl": "rule p when $t : T ( true ) then end",
            "shadow_drl": "rule s when $t : T ( true ) then end",
            "fact": {"t": {}},
            "run_id": "shadow-gen",
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "SIMULATION_FAILED"


def test_post_simulations_coverage_rule_evaluation_error_propagates() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/coverage",
        json={
            "drl": "rule r when $t : T ( $t.amount > 0 ) then end",
            "facts": [{}],
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "UNBOUND_OR_NULL"


def test_post_simulations_coverage_generic_exception() -> None:
    deps = AppDeps()

    def boom(_d: str, _f: list) -> None:
        raise RuntimeError("coverage boom")

    deps.sim.analyze_coverage = boom  # type: ignore[assignment]
    c = TestClient(create_app(deps))
    r = c.post(
        "/simulations/coverage",
        json={"drl": "rule r when $t : T ( true ) then end", "facts": [{}]},
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "SIMULATION_FAILED"


def test_post_counterfactual_generic_exception() -> None:
    deps = AppDeps()
    n = [0]

    def flaky(_d: str, fact: dict) -> MagicMock:
        n[0] += 1
        if n[0] == 1:
            raise RuntimeError("first run fails")
        m = MagicMock()
        m.fired = False
        m.action = {}
        return m

    deps.sim.run = flaky  # type: ignore[assignment]
    c = TestClient(create_app(deps))
    r = c.post(
        "/simulations/counterfactual",
        json={
            "drl": "rule r when $t : T ( true ) then end",
            "baseline_fact": {"t": {}},
            "candidate_fact": {"t": {}},
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 400


def test_post_counterfactual_rule_evaluation_on_baseline() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/counterfactual",
        json={
            "drl": "rule r when $t : T ( $t.x > 3 ) then result.z = 1; end",
            "baseline_fact": {},
            "candidate_fact": {"t": {"x": 5}},
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 400


def test_time_travel_capture_rule_evaluation_error_propagates() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/debug/time-travel/capture",
        json={
            "run_id": "tt-rev",
            "drl": "rule r when $t : T ( $t.z > 0 ) then end",
            "fact": {},
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "UNBOUND_OR_NULL"


def test_time_travel_capture_generic_exception() -> None:
    deps = AppDeps()

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("tt cap")

    deps.sim.run = boom  # type: ignore[assignment]
    c = TestClient(create_app(deps))
    r = c.post(
        "/debug/time-travel/capture",
        json={
            "run_id": "tt-1",
            "drl": "rule r when $t : T ( true ) then end",
            "fact": {"t": {}},
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "TIME_TRAVEL_FAILED"


def test_time_travel_replay_parse_error_and_generic() -> None:
    deps = AppDeps()
    sid = deps.debug_runs.append(
        [
            {
                "run_id": "rr1",
                "drl": "rule r when $t : T ( true ) then end",
                "fact_json": '{"t": {}}',
                "ts": "2020-01-01T00:00:00",
            }
        ]
    )

    def parse_boom(_d: str, _f: dict) -> None:
        raise ValueError("lexer issue")

    deps.sim.run = parse_boom  # type: ignore[assignment]
    c = TestClient(create_app(deps))
    r = c.post(
        "/debug/time-travel/replay",
        json={"snapshot_id": sid, "run_id": "rr1"},
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 422

    def gen_boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("replay boom")

    deps.sim.run = gen_boom  # type: ignore[assignment]
    c2 = TestClient(create_app(deps))
    r2 = c2.post(
        "/debug/time-travel/replay",
        json={"snapshot_id": sid, "run_id": "rr1"},
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r2.status_code == 400
    assert r2.json()["detail"]["code"] == "TIME_TRAVEL_FAILED"


def test_sim_chain_generic_exception() -> None:
    deps = AppDeps()

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("chain boom")

    deps.sim.run_chain = boom  # type: ignore[assignment]
    c = TestClient(create_app(deps))
    r = c.post(
        "/simulations/chain",
        json={"drl": "rule a when $t : T ( true ) then end", "fact": {"t": {}}},
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "SIMULATION_FAILED"


def test_sim_chain_rule_evaluation_error_lineage() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/chain",
        json={
            "drl": "rule a when $t : T ( $t.n > 0 ) then end",
            "fact": {},
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 400


def test_ai_suggestion_simulate_parse_error_and_rev() -> None:
    deps = AppDeps()
    out = deps.ai.create_rule_suggestions(
        namespace="default",
        payload={"rule_handle": "z", "facts": []},
        principal="p",
    )
    sid = out[0].id
    hdr = {"X-Roles": "ai_reviewer", "X-Tenant-Id": "default"}

    def parse_err(*_a: object, **_k: object) -> None:
        raise ParseError("bad")

    deps.sim.run = parse_err  # type: ignore[assignment]
    c = TestClient(create_app(deps))
    pe = c.post(f"/ai/suggestions/{sid}/simulate", json={"fact": {"t": {}}}, headers=hdr)
    assert pe.status_code == 422

    def rev_raise(*_a: object, **_k: object) -> None:
        raise RuleEvaluationError("boom", code="X")

    deps.sim.run = rev_raise  # type: ignore[assignment]
    r2 = c.post(f"/ai/suggestions/{sid}/simulate", json={"fact": {"t": {}}}, headers=hdr)
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "X"


def test_ai_suggestion_simulate_generic_exception() -> None:
    deps = AppDeps()
    out = deps.ai.create_rule_suggestions(
        namespace="default",
        payload={"rule_handle": "x", "facts": []},
        principal="p",
    )
    sid = out[0].id

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("ai sim")

    deps.sim.run = boom  # type: ignore[assignment]
    c = TestClient(create_app(deps))
    r = c.post(
        f"/ai/suggestions/{sid}/simulate",
        json={"fact": {"t": {}}},
        headers={"X-Roles": "ai_reviewer", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "AI_SIMULATION_FAILED"

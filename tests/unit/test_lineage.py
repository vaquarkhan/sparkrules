from __future__ import annotations

from fastapi.testclient import TestClient

from sre.api import AppDeps, create_app
from sre.runtime.lineage import InMemoryLineageSink, make_lineage_event


def test_make_lineage_event_and_sink() -> None:
    e = make_lineage_event("START", "r1", payload={"x": 1})
    assert e.event_type == "START"
    assert e.run_id == "r1"
    s = InMemoryLineageSink()
    s.emit(e)
    assert len(s.events) == 1


def test_lineage_emitted_for_counterfactual() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    h = {"X-Roles": "run_operator", "X-Tenant-Id": "default"}
    r = c.post(
        "/simulations/counterfactual",
        json={
            "drl": """
rule r
when
$t : T ( $t.x > 0 )
then
result.v = 1;
end
""",
            "baseline_fact": {"t": {"x": 1}},
            "candidate_fact": {"t": {"x": 5}},
        },
        headers=h,
    )
    assert r.status_code == 200
    ev = c.get("/lineage/events", headers={"X-Roles": "platform_admin"}).json()
    cf = [x for x in ev if str(x.get("run_id", "")).startswith("sim-cf-")]
    assert any(x["event_type"] == "START" for x in cf)
    assert any(x["event_type"] == "COMPLETE" for x in cf)
    st = next(x for x in cf if x["event_type"] == "START")
    assert (st.get("payload") or {}).get("context", {}).get("mode") == "SIMULATION_COUNTERFACTUAL"


def test_lineage_emitted_for_simulation_and_dq() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    s = c.post(
        "/simulations",
        json={
            "drl": "rule r when $t : T ( true ) then result.ok = true; end",
            "fact": {"t": {}},
        },
    )
    assert s.status_code == 200
    d = c.post(
        "/dq/evaluate",
        json={
            "fact": {"id": None},
            "checks": [{"kind": "not_null", "field": "id"}],
            "run_id": "dq-1",
        },
        headers={"X-Roles": "dq_steward", "X-Tenant-Id": "default"},
    )
    assert d.status_code == 200
    ev = c.get("/lineage/events", headers={"X-Roles": "platform_admin"})
    assert ev.status_code == 200
    rows = ev.json()
    assert any(x["event_type"] == "START" for x in rows)
    assert any(x["event_type"] == "COMPLETE" for x in rows)
    dq_rows = c.get(
        "/lineage/events",
        params={"run_id": "dq-1"},
        headers={"X-Roles": "platform_admin"},
    ).json()
    assert len(dq_rows) >= 2
    assert all(x["run_id"] == "dq-1" for x in dq_rows)


def test_lineage_fail_event_on_bad_chain() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/chain",
        json={"drl": "not valid drl", "fact": {}},
    )
    assert r.status_code == 422
    ev = c.get("/lineage/events", headers={"X-Roles": "platform_admin"}).json()
    assert any(x["event_type"] == "FAIL" for x in ev)


def test_lineage_fail_event_on_bad_single_simulation() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations",
        json={"drl": "broken drl", "fact": {}},
    )
    assert r.status_code == 422
    ev = c.get("/lineage/events", headers={"X-Roles": "platform_admin"}).json()
    assert any(x["event_type"] == "FAIL" and str(x["run_id"]).startswith("sim-") for x in ev)
    fail = next(
        x
        for x in ev
        if x["event_type"] == "FAIL" and str(x["run_id"]).startswith("sim-")
    )
    assert "inputs" in fail["payload"]
    assert "principal" in fail["payload"]


def test_lineage_shadow_success_and_fail() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    ok = c.post(
        "/simulations/shadow",
        json={
            "primary_drl": "rule a when $t : T ( true ) then result.d = \"a\"; end",
            "shadow_drl": "rule b when $t : T ( true ) then result.d = \"b\"; end",
            "fact": {"t": {}},
            "run_id": "shadow-ok",
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert ok.status_code == 200
    bad = c.post(
        "/simulations/shadow",
        json={
            "primary_drl": "bad drl",
            "shadow_drl": "rule b when $t : T ( true ) then result.d = \"b\"; end",
            "fact": {"t": {}},
            "run_id": "shadow-bad",
        },
        headers={"X-Roles": "run_operator", "X-Tenant-Id": "default"},
    )
    assert bad.status_code == 422
    ev = c.get("/lineage/events", headers={"X-Roles": "platform_admin"}).json()
    assert any(x["event_type"] == "COMPLETE" and x["run_id"] == "shadow-ok" for x in ev)
    assert any(x["event_type"] == "FAIL" and x["run_id"] == "shadow-bad" for x in ev)

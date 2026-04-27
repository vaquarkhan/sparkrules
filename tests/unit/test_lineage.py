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
    assert r.status_code == 400
    ev = c.get("/lineage/events", headers={"X-Roles": "platform_admin"}).json()
    assert any(x["event_type"] == "FAIL" for x in ev)


def test_lineage_fail_event_on_bad_single_simulation() -> None:
    app = create_app(AppDeps())
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post(
        "/simulations",
        json={"drl": "broken drl", "fact": {}},
    )
    assert r.status_code == 500
    ev = c.get("/lineage/events", headers={"X-Roles": "platform_admin"}).json()
    assert any(x["event_type"] == "FAIL" and str(x["run_id"]).startswith("sim-") for x in ev)

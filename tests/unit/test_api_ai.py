from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from sre.api import AppDeps, create_app


def test_ai_suggest_and_list() -> None:
    c = TestClient(create_app(AppDeps()))
    r = c.post(
        "/ai/suggest-rules",
        json={"namespace": "default", "rule_handle": "hx", "facts": [{"x": 1}]},
        headers={"X-Roles": "ai_reviewer", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    sid = rows[0]["id"]
    l = c.get("/ai/suggestions", headers={"X-Roles": "ai_reviewer", "X-Tenant-Id": "default"})
    assert l.status_code == 200
    assert any(x["id"] == sid for x in l.json())


def test_ai_approve_requires_simulator_evidence() -> None:
    deps = AppDeps()
    app = create_app(deps)
    c = TestClient(app)
    r = c.post(
        "/ai/suggest-rules",
        json={"namespace": "default", "rule_handle": "hx", "facts": []},
        headers={"X-Roles": "ai_reviewer", "X-Tenant-Id": "default"},
    )
    sid = r.json()[0]["id"]
    a = c.post(f"/ai/suggestions/{sid}/approve", headers={"X-Roles": "ai_reviewer", "X-Tenant-Id": "default"})
    assert a.status_code == 400
    s = deps.ai.store.get(sid)
    deps.ai.store.upsert(replace(s, simulator_result={"ok": True}))
    a2 = c.post(f"/ai/suggestions/{sid}/approve", headers={"X-Roles": "ai_reviewer", "X-Tenant-Id": "default"})
    assert a2.status_code == 200
    assert a2.json()["status"] == "APPROVED"
    rj = c.post(f"/ai/suggestions/{sid}/reject", headers={"X-Roles": "ai_reviewer", "X-Tenant-Id": "default"})
    assert rj.status_code == 200
    assert rj.json()["status"] == "REJECTED"


def test_ai_other_endpoints() -> None:
    c = TestClient(create_app(AppDeps()))
    m = c.post("/ai/mine-dq-rules", json={"field": "id", "namespace": "default"}, headers={"X-Roles": "dq_steward", "X-Tenant-Id": "default"})
    assert m.status_code == 200
    assert m.json()["items"]
    d = c.post("/ai/analyze-drift", json={"namespace": "default", "handle": "h", "history": [0.1]}, headers={"X-Roles": "ai_reviewer", "X-Tenant-Id": "default"})
    assert d.status_code == 200
    e = c.post("/ai/explain-rule", json={"drl": "rule r when $t : T ( true ) then end"}, headers={"X-Roles": "rule_reader", "X-Tenant-Id": "default"})
    assert e.status_code == 200
    assert "explanation" in e.json()

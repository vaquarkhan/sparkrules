from __future__ import annotations

from fastapi.testclient import TestClient

from sparkrules.api import AppDeps, create_app


_DRL = """
rule r
when
$t : T ( true )
then
end
"""


def test_rbac_blocks_rule_create_for_reader() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/rules",
        json={"rule_handle": "r1", "group": "g", "namespace": "n1", "drl": _DRL},
        headers={"X-Roles": "rule_reader", "X-Tenant-Id": "n1", "X-Principal": "u1"},
    )
    assert r.status_code == 403


def test_tenant_namespace_mismatch_rejected() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/rules",
        json={"rule_handle": "r1", "group": "g", "namespace": "nsA", "drl": _DRL},
        headers={"X-Roles": "rule_admin", "X-Tenant-Id": "nsB", "X-Principal": "u2"},
    )
    assert r.status_code == 403
    assert "tenant" in r.json()["detail"]


def test_rules_assets_default_to_tenant_scope() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    h = {"X-Roles": "rule_admin", "X-Tenant-Id": "n1", "X-Principal": "u3"}
    c.post(
        "/rules", json={"rule_handle": "a", "group": "g", "namespace": "n1", "drl": _DRL}, headers=h
    )
    c.post("/rules", json={"rule_handle": "b", "group": "g", "namespace": "n2", "drl": _DRL})
    rows = c.get("/rules/assets", headers={"X-Roles": "rule_reader", "X-Tenant-Id": "n1"}).json()
    assert all(x["namespace"] == "n1" for x in rows)


def test_mutating_endpoints_write_audit_log() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    h = {"X-Roles": "rule_admin", "X-Tenant-Id": "n9", "X-Principal": "auditor-user"}
    c.post(
        "/rules", json={"rule_handle": "z", "group": "g", "namespace": "n9", "drl": _DRL}, headers=h
    )
    c.post("/governance/sync-dev", json={"namespace": "n9", "rule_handle": "z"}, headers=h)
    logs = c.get("/audit/logs", headers={"X-Roles": "platform_admin"}).json()
    assert len(logs) >= 2
    assert any(x["action"] == "create_rule" for x in logs)
    assert any(x["action"] == "governance_sync_dev" for x in logs)
    assert all("request_hash" in x for x in logs)


def test_audit_log_tenant_filter() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    h1 = {"X-Roles": "rule_admin", "X-Tenant-Id": "t1", "X-Principal": "u1"}
    h2 = {"X-Roles": "rule_admin", "X-Tenant-Id": "t2", "X-Principal": "u2"}
    c.post(
        "/rules",
        json={"rule_handle": "a1", "group": "g", "namespace": "t1", "drl": _DRL},
        headers=h1,
    )
    c.post(
        "/rules",
        json={"rule_handle": "a2", "group": "g", "namespace": "t2", "drl": _DRL},
        headers=h2,
    )
    rows = c.get(
        "/audit/logs", params={"tenant_id": "t1"}, headers={"X-Roles": "platform_admin"}
    ).json()
    assert rows
    assert all(x["tenant_id"] == "t1" for x in rows)


def test_governance_non_admin_scoped_to_tenant() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    c.post("/rules", json={"rule_handle": "nsr", "group": "g", "namespace": "tn1", "drl": _DRL})
    ns = c.get(
        "/governance/namespaces", headers={"X-Roles": "rule_reader", "X-Tenant-Id": "tn1"}
    ).json()
    assert ns == ["tn1"]
    c.post("/governance/sync-dev", json={"namespace": "tn1", "rule_handle": "nsr"})
    pins = c.get(
        "/governance/pins", headers={"X-Roles": "rule_reader", "X-Tenant-Id": "tn1"}
    ).json()
    assert pins
    assert all(x["namespace"] == "tn1" for x in pins)


def test_rules_list_and_groups_scoped_to_tenant() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    c.post("/rules", json={"rule_handle": "r1", "group": "g1", "namespace": "t1", "drl": _DRL})
    c.post("/rules", json={"rule_handle": "r2", "group": "g2", "namespace": "t2", "drl": _DRL})
    h1 = {"X-Roles": "rule_reader", "X-Tenant-Id": "t1"}
    assert c.get("/rules", headers=h1).json() == ["r1"]
    assert c.get("/rules/groups", headers=h1).json() == ["g1"]


def test_export_and_diff_enforce_tenant_access() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    c.post("/rules", json={"rule_handle": "r1", "group": "g", "namespace": "t1", "drl": _DRL})
    c.post("/rules", json={"rule_handle": "r2", "group": "g", "namespace": "t2", "drl": _DRL})
    h1 = {"X-Roles": "rule_reader", "X-Tenant-Id": "t1"}
    h2 = {"X-Roles": "rule_reader", "X-Tenant-Id": "t2"}
    j1 = c.get("/rules/export", headers=h1).json()
    assert all(x["namespace"] == "t1" for x in j1["rules"])
    j2 = c.get("/rules/export", headers=h2).json()
    assert all(x["namespace"] == "t2" for x in j2["rules"])
    denied = c.get(
        "/rules/diff", params={"handle": "r2", "version_a": 1, "version_b": 1}, headers=h1
    )
    assert denied.status_code == 403
    scoped = c.get("/rules/export", params={"namespace": "t1"}, headers=h1)
    assert scoped.status_code == 200
    assert all(x["namespace"] == "t1" for x in scoped.json()["rules"])


def test_role_matrix_blocks_unknown_role_on_secured_endpoints() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    h = {"X-Roles": "guest", "X-Tenant-Id": "default"}
    assert (
        c.post("/simulations", json={"drl": _DRL, "fact": {"t": {}}}, headers=h).status_code == 403
    )
    assert c.post("/rules/validate", json={"drl": _DRL}, headers=h).status_code == 403
    assert c.get("/system/deployment", headers=h).status_code == 403
    assert c.get("/workbench/api/guided-fields", headers=h).status_code == 403
    assert c.get("/governance/environments", headers=h).status_code == 403

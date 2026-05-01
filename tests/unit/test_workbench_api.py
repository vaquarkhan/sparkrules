from __future__ import annotations

from fastapi.testclient import TestClient

from sparkrules.api import AppDeps, create_app


def test_rules_assets_empty() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.get("/rules/assets")
    assert r.status_code == 200
    assert r.json() == []


def test_rules_validate_and_assets_roundtrip() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    drl = """
    rule t1
when
$t : T ( true )
then
end
"""
    v = c.post("/rules/validate", json={"drl": drl})
    assert v.status_code == 200
    p = c.post(
        "/rules",
        json={"rule_handle": "h1", "group": "g1", "drl": drl},
    )
    assert p.status_code == 200
    a = c.get("/rules/assets")
    assert a.status_code == 200
    rows = a.json()
    assert len(rows) == 1
    assert rows[0]["rule_handle"] == "h1"
    assert rows[0]["rule_group"] == "g1"
    assert "T ( true )" in rows[0]["drl"]
    r = c.patch(
        "/rules/h1/version/1",
        json={"is_active": False},
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    a2 = c.get("/rules/assets")
    assert a2.json()[0]["is_active"] is False

    g = c.get("/rules/h1/version/1")
    assert g.status_code == 200
    gj = g.json()
    assert gj["rule_handle"] == "h1"
    assert gj["version"] == 1
    assert "T ( true )" in gj["drl"]


def test_rules_validate_422() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post("/rules/validate", json={"drl": "not drl at all {{"})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "DRL_PARSE_ERROR"


def test_deployment_status() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.get("/system/deployment")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert "engine_config" in j
    assert j["engine_config"]["sparkrules.platform"] == "local"


def test_guided_fields_default() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.get("/workbench/api/guided-fields")
    assert r.status_code == 200
    j = r.json()
    assert "fields" in j
    assert isinstance(j["fields"], list)


def test_patch_rule_version_404() -> None:
    c = TestClient(create_app(AppDeps()))
    r = c.patch(
        "/rules/none/version/1",
        json={"is_active": False},
    )
    assert r.status_code == 404


def test_patch_rule_version_active_409_overlap() -> None:
    drl = """
    rule t1
when
$t : T ( true )
then
end
"""
    c = TestClient(create_app(AppDeps()))
    c.post(
        "/rules",
        json={"rule_handle": "ov", "group": "g", "drl": drl},
    )
    c.patch(
        "/rules/ov/version/1",
        json={"is_active": False},
    )
    c.post(
        "/rules",
        json={"rule_handle": "ov", "group": "g", "drl": drl.replace("true", "false")},
    )
    r = c.patch(
        "/rules/ov/version/1",
        json={"is_active": True},
    )
    assert r.status_code == 409


def test_workbench_static_index() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.get("/workbench/index.html")
    assert r.status_code == 200
    assert b"SparkRules Workbench" in r.content
    assert b"sparkrules-logo.png" in r.content
    assert b'id="api-key"' in r.content
    assert b"view-governance" in r.content
    assert b"btn-export-pack" in r.content
    assert b"view-overview" in r.content
    assert b"btn-theme" in r.content
    assert b"sim-batch-max" in r.content
    assert b"adv-dq-dashboard" in r.content
    logo = c.get("/workbench/sparkrules-logo.png")
    assert logo.status_code == 200
    assert "png" in logo.headers.get("content-type", "")
    assert len(logo.content) > 1000

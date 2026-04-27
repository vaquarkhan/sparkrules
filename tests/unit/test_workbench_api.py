from __future__ import annotations

from fastapi.testclient import TestClient

from sre.api import AppDeps, create_app


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


def test_rules_validate_400() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post("/rules/validate", json={"drl": "not drl at all {{"})
    assert r.status_code == 400


def test_deployment_status() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.get("/system/deployment")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert "engine_config" in j
    assert j["engine_config"]["sre.platform"] == "local"


def test_guided_fields_default() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.get("/workbench/api/guided-fields")
    assert r.status_code == 200
    j = r.json()
    assert "fields" in j
    assert isinstance(j["fields"], list)


def test_workbench_static_index() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.get("/workbench/index.html")
    assert r.status_code == 200
    assert b"SparkRules Workbench" in r.content
    assert b'id="api-key"' in r.content
    assert b"view-governance" in r.content
    assert b"btn-export-pack" in r.content

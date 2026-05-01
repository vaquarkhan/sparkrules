from __future__ import annotations

from fastapi.testclient import TestClient

from sparkrules.api import AppDeps, create_app


def _drl() -> str:
    return """
rule t1
when
$t : T ( true )
then
end
"""


def test_rules_groups() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    assert c.get("/rules/groups").json() == []
    c.post(
        "/rules",
        json={"rule_handle": "h1", "group": "g1", "drl": _drl()},
    )
    assert c.get("/rules/groups").json() == ["g1"]


def test_rules_assets_filter_q() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    c.post(
        "/rules",
        json={"rule_handle": "foo_rule", "group": "g", "drl": _drl()},
    )
    r = c.get("/rules/assets", params={"q": "foo"})
    assert r.status_code == 200
    assert len(r.json()) == 1
    r2 = c.get("/rules/assets", params={"q": "nomatch"})
    assert r2.json() == []


def test_rules_assets_filter_group() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    c.post(
        "/rules",
        json={"rule_handle": "a", "group": "alpha", "drl": _drl()},
    )
    c.post(
        "/rules",
        json={"rule_handle": "b", "group": "beta", "drl": _drl()},
    )
    r = c.get("/rules/assets", params={"group": "beta"})
    assert len(r.json()) == 1
    assert r.json()[0]["rule_handle"] == "b"


def test_rules_import_validation_422() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/rules/import",
        json={
            "items": [
                {
                    "rule_handle": "bad",
                    "group": "g",
                    "drl": "this is not valid drl {{{",
                }
            ],
        },
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "DRL_PARSE_ERROR"


def test_rules_diff_404() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.get(
        "/rules/diff", params={"handle": "nope", "version_a": 1, "version_b": 2}
    )
    assert r.status_code == 404


def test_rules_diff_and_export_import() -> None:
    deps = AppDeps()
    app = create_app(deps)
    c = TestClient(app)
    d1 = _drl()
    c.post(
        "/rules",
        json={"rule_handle": "h", "group": "g", "drl": d1},
    )
    v1 = deps.store.get("h", 1)
    deps.store.update("h", v1.with_updates(is_active=False))
    d2 = d1.replace("true", "false")
    c.post(
        "/rules",
        json={"rule_handle": "h", "group": "g", "drl": d2},
    )
    diff = c.get(
        "/rules/diff", params={"handle": "h", "version_a": 1, "version_b": 2}
    )
    assert diff.status_code == 200
    j = diff.json()
    assert j["version_a"] == 1
    assert j["version_b"] == 2
    assert "unified_diff" in j

    ex = c.get("/rules/export")
    assert ex.status_code == 200
    pack = ex.json()
    assert pack["format"] == "sparkrules-rulepack-1"
    assert len(pack["rules"]) >= 1

    app2 = create_app(AppDeps())
    c2 = TestClient(app2)
    imp = c2.post(
        "/rules/import",
        json={
            "items": [
                {
                    "rule_handle": "imp1",
                    "group": "g2",
                    "drl": _drl(),
                }
            ],
        },
    )
    assert imp.status_code == 200
    assert imp.json()["count"] == 1

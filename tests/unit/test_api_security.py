from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sparkrules.api import AppDeps, create_app

_VALID_DRL = """
rule t1
when
$t : T ( true )
then
end
"""


def test_no_api_key_middleware_allows_post() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post("/rules/validate", json={"drl": _VALID_DRL})
    assert r.status_code == 200


def test_api_key_set_blocks_post_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_API_KEY", "secret")
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post("/rules/validate", json={"drl": _VALID_DRL})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid or missing API key"


def test_api_key_allows_public_get_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPARKRULES_API_KEY", "secret")
    app = create_app(AppDeps())
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    r_docs = c.get("/docs")
    assert r_docs.status_code in (200, 307)


def test_api_key_blocks_sensitive_get_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPARKRULES_API_KEY", "secret")
    app = create_app(AppDeps())
    c = TestClient(app)
    assert c.get("/rules/assets").status_code == 401
    assert c.get("/rules/export").status_code == 401
    assert c.get("/governance/namespaces").status_code == 401
    assert c.get("/system/deployment").status_code == 401
    a = c.get(
        "/rules/assets",
        headers={"X-API-Key": "secret"},
    )
    assert a.status_code == 200
    ex = c.get(
        "/rules/export",
        headers={"X-API-Key": "secret"},
    )
    assert ex.status_code == 200


def test_api_key_post_with_x_api_key_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_API_KEY", "secret")
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/rules/validate",
        json={"drl": _VALID_DRL},
        headers={"X-API-Key": "secret"},
    )
    assert r.status_code == 200


def test_api_key_post_with_bearer_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_API_KEY", "secret")
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/rules/validate",
        json={"drl": _VALID_DRL},
        headers={"Authorization": "Bearer secret"},
    )
    assert r.status_code == 200


def test_options_pretflight_skips_key_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPARKRULES_API_KEY", "secret")
    c = TestClient(create_app(AppDeps()))
    r = c.options("/rules/assets")
    assert r.status_code in (200, 204, 405)


def test_api_key_post_wrong_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_API_KEY", "secret")
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/rules/validate",
        json={"drl": _VALID_DRL},
        headers={"X-API-Key": "wrong"},
    )
    assert r.status_code == 401

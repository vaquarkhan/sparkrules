from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sparkrules.api import AppDeps, create_app
from sparkrules.api.workbench_auth import is_path_exempt_from_workbench_gate, verify_workbench_token


def test_exempt_paths_and_invalid_token() -> None:
    assert is_path_exempt_from_workbench_gate("/health") is True
    assert is_path_exempt_from_workbench_gate("/workbench/index.html") is True
    assert verify_workbench_token("") is None
    assert verify_workbench_token("not-a-token") is None


def test_workbench_auth_config_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPARKRULES_WORKBENCH_AUTH", raising=False)
    monkeypatch.delenv("SPARKRULES_DISABLE_WORKBENCH_GATE", raising=False)
    c = TestClient(create_app(AppDeps()))
    r = c.get("/api/workbench/auth/config")
    assert r.status_code == 200
    j = r.json()
    assert j["auth_enabled"] is False
    assert j["gate_active"] is False


def test_workbench_login_and_token_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_WORKBENCH_AUTH", "1")
    monkeypatch.setenv("SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS", "1")
    monkeypatch.delenv("SPARKRULES_DISABLE_WORKBENCH_GATE", raising=False)
    c = TestClient(create_app(AppDeps()))
    assert c.get("/api/workbench/auth/config").json()["gate_active"] is True
    assert c.get("/rules/assets").status_code == 401
    r = c.post("/api/workbench/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    tok = r.json()["token"]
    assert r.json()["principal"] == "admin"
    ok = c.get("/rules/assets", headers={"X-Workbench-Token": tok})
    assert ok.status_code == 200


def test_workbench_login_disabled_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPARKRULES_WORKBENCH_AUTH", raising=False)
    c = TestClient(create_app(AppDeps()))
    r = c.post("/api/workbench/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "WORKBENCH_AUTH_DISABLED"


def test_workbench_login_bad_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_WORKBENCH_AUTH", "1")
    monkeypatch.setenv("SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS", "1")
    c = TestClient(create_app(AppDeps()))
    r = c.post("/api/workbench/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401
    d = r.json()["detail"]
    assert d["code"] == "WORKBENCH_LOGIN_FAILED"
    assert d["hint_username"] == "admin"
    assert d["password_configured_on_server"] is False


def test_workbench_login_uppercase_username_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_WORKBENCH_AUTH", "1")
    monkeypatch.delenv("SPARKRULES_WORKBENCH_PASSWORD", raising=False)
    monkeypatch.delenv("SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS", raising=False)
    c = TestClient(create_app(AppDeps()))
    r = c.post("/api/workbench/auth/login", json={"username": "ADMIN", "password": "admin"})
    assert r.status_code == 200
    assert r.json()["principal"] == "admin"


def test_workbench_login_works_without_explicit_default_credentials_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only SPARKRULES_WORKBENCH_AUTH=1 is required for admin/admin when no custom password is set."""
    monkeypatch.setenv("SPARKRULES_WORKBENCH_AUTH", "1")
    monkeypatch.delenv("SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS", raising=False)
    monkeypatch.delenv("SPARKRULES_WORKBENCH_PASSWORD", raising=False)
    c = TestClient(create_app(AppDeps()))
    r = c.post("/api/workbench/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    assert r.json()["principal"] == "admin"


def test_workbench_api_key_bypasses_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_WORKBENCH_AUTH", "1")
    monkeypatch.setenv("SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS", "1")
    monkeypatch.setenv("SPARKRULES_API_KEY", "sekrit-key")
    c = TestClient(create_app(AppDeps()))
    r = c.get("/rules/assets", headers={"X-API-Key": "sekrit-key"})
    assert r.status_code == 200


def test_workbench_auth_config_includes_gate_active(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_WORKBENCH_AUTH", "1")
    monkeypatch.setenv("SPARKRULES_DISABLE_WORKBENCH_GATE", "1")
    c = TestClient(create_app(AppDeps()))
    r = c.get("/api/workbench/auth/config")
    assert r.status_code == 200
    j = r.json()
    assert j["auth_enabled"] is True
    assert j["gate_active"] is False


def test_disable_workbench_gate_allows_assets_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPARKRULES_WORKBENCH_AUTH", "1")
    monkeypatch.setenv("SPARKRULES_DISABLE_WORKBENCH_GATE", "1")
    c = TestClient(create_app(AppDeps()))
    assert c.get("/rules/assets").status_code == 200

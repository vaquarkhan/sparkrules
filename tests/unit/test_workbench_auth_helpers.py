from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest

from sparkrules.api import workbench_auth as wa


def test_workbench_http_gate_respects_disable_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPARKRULES_DISABLE_WORKBENCH_GATE", raising=False)
    monkeypatch.delenv("SPARKRULES_WORKBENCH_AUTH", raising=False)
    assert wa.workbench_http_gate_active() is False
    monkeypatch.setenv("SPARKRULES_WORKBENCH_AUTH", "1")
    assert wa.workbench_http_gate_active() is True
    monkeypatch.setenv("SPARKRULES_DISABLE_WORKBENCH_GATE", "1")
    assert wa.workbench_http_gate_active() is False


def test_normalize_workbench_username() -> None:
    assert wa.normalize_workbench_username("=admin") == "admin"
    assert wa.normalize_workbench_username("  Admin  ") == "admin"
    assert wa.normalize_workbench_username("") == ""


def test_verify_credentials_case_insensitive_when_implicit_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS", raising=False)
    monkeypatch.delenv("SPARKRULES_WORKBENCH_PASSWORD", raising=False)
    assert wa.verify_credentials("ADMIN", "admin") is True
    assert wa.verify_credentials("=admin", "admin") is True


def test_verify_credentials_implicit_dev_admin_when_no_password_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS", raising=False)
    monkeypatch.delenv("SPARKRULES_WORKBENCH_PASSWORD", raising=False)
    assert wa.verify_credentials("admin", "admin") is True


def test_verify_credentials_rejects_when_defaults_explicitly_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS", "0")
    monkeypatch.delenv("SPARKRULES_WORKBENCH_PASSWORD", raising=False)
    assert wa.verify_credentials("admin", "admin") is False


def test_verify_credentials_compare_digest_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS", "1")
    monkeypatch.setenv("SPARKRULES_WORKBENCH_USER", "admin")

    def _boom(a: bytes, b: bytes) -> bool:
        raise ValueError()

    monkeypatch.setattr(wa.hmac, "compare_digest", _boom)
    assert wa.verify_credentials("admin", "admin") is False


def test_verify_workbench_token_wrong_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPARKRULES_WORKBENCH_SECRET", raising=False)
    monkeypatch.delenv("SPARKRULES_API_KEY", raising=False)
    tok = wa.create_workbench_token("u1")
    body, _sig = tok.split(".", 1)
    bad = f"{body}.deadbeef"
    assert wa.verify_workbench_token(bad) is None


def test_verify_workbench_token_expired() -> None:
    payload = json.dumps({"u": "x", "exp": int(time.time()) - 10}, separators=(",", ":")).encode(
        "utf-8"
    )
    body = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    sig = hmac.new(
        wa._secret(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    tok = f"{body}.{sig}"
    assert wa.verify_workbench_token(tok) is None


def test_verify_workbench_token_malformed_payload() -> None:
    garbage = b"not-json"
    body = base64.urlsafe_b64encode(garbage).decode("ascii").rstrip("=")
    sig = hmac.new(wa._secret(), garbage, hashlib.sha256).hexdigest()
    tok = f"{body}.{sig}"
    assert wa.verify_workbench_token(tok) is None

"""Production-safe default roles (no implicit platform_admin)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sre.api import AppDeps, create_app


def test_post_rules_forbidden_without_roles_when_dev_superuser_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SPARKRULES_DEV_ALLOW_DEFAULT_SUPERUSER", raising=False)
    monkeypatch.delenv("SPARKRULES_LOCAL_DEFAULT_ROLES", raising=False)
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/rules",
        json={
            "rule_handle": "nope",
            "group": "g",
            "namespace": "default",
            "drl": "rule r when $t : T ( true ) then end",
        },
    )
    assert r.status_code == 403

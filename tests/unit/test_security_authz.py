from __future__ import annotations

import base64
import json

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from sre.api.security import (
    _bearer_token,
    _decode_jwt_claims_unverified,
    principal_from_request,
    require_any_role,
    require_tenant_match,
)


def _req(headers: dict[str, str] | None = None) -> Request:
    h = headers or {}
    raw = [(k.lower().encode("utf-8"), v.encode("utf-8")) for k, v in h.items()]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": raw})


def _jwt(payload: dict[str, object]) -> str:
    head = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode().rstrip("=")
    return f"{head}.{body}."


def test_bearer_token_helper() -> None:
    assert _bearer_token(_req({"Authorization": "Bearer abc"})) == "abc"
    assert _bearer_token(_req({"Authorization": "Basic z"})) is None


def test_decode_jwt_claims_unverified_paths() -> None:
    assert _decode_jwt_claims_unverified("x") == {}
    assert _decode_jwt_claims_unverified("a.b.") == {}
    tok = _jwt({"sub": "u1", "tenant_id": "n1", "roles": ["rule_admin"]})
    c = _decode_jwt_claims_unverified(tok)
    assert c["sub"] == "u1"
    not_obj_payload = base64.urlsafe_b64encode(b"[1,2,3]").decode("utf-8").rstrip("=")
    assert _decode_jwt_claims_unverified(f"aa.{not_obj_payload}.") == {}


def test_principal_from_headers_and_claims() -> None:
    p1 = principal_from_request(_req({"X-Principal": "u2", "X-Tenant-Id": "t2", "X-Roles": "rule_reader,rule_author"}))
    assert p1.principal == "u2"
    assert p1.tenant_id == "t2"
    assert "rule_author" in p1.roles

    tok = _jwt({"email": "x@y", "tid": "tt", "role": "rule_admin"})
    p2 = principal_from_request(_req({"Authorization": f"Bearer {tok}"}))
    assert p2.principal == "x@y"
    assert p2.tenant_id == "tt"
    assert p2.roles == ("rule_admin",)

    tok2 = _jwt({"sub": "u3", "tenant_id": "t3", "roles": ["rule_reader", "dq_steward"]})
    p4 = principal_from_request(_req({"Authorization": f"Bearer {tok2}"}))
    assert p4.roles == ("rule_reader", "dq_steward")

    p3 = principal_from_request(_req())
    assert p3.roles == ("platform_admin",)


def test_require_any_role_and_tenant_checks() -> None:
    p = principal_from_request(_req({"X-Roles": "rule_reader", "X-Tenant-Id": "n1"}))
    require_any_role(p, {"rule_reader"})
    with pytest.raises(HTTPException):
        require_any_role(p, {"rule_admin"})
    require_tenant_match(p, "n1")
    with pytest.raises(HTTPException):
        require_tenant_match(p, "n2")
    with pytest.raises(HTTPException):
        require_tenant_match(p, "")


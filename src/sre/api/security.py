from __future__ import annotations

import os
import json
import base64
import binascii
from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import FastAPI, HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


def _env_api_key() -> str | None:
    v = os.environ.get("SPARKRULES_API_KEY", "").strip()
    return v or None


def _supplied_key(request: Request) -> str:
    h = request.headers.get("x-api-key", "")
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return h


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def _decode_jwt_claims_unverified(token: str) -> dict[str, object]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    pad = "=" * ((4 - len(payload) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload + pad).decode("utf-8")
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except (ValueError, binascii.Error, json.JSONDecodeError):
        return {}
    return {}


@dataclass(frozen=True, slots=True)
class Principal:
    principal: str
    tenant_id: str
    roles: tuple[str, ...]


def principal_from_request(request: Request) -> Principal:
    """Extract principal/tenant/roles from Bearer claims or explicit headers.

    Header fallback is useful in local/dev and tests:
    - X-Principal
    - X-Tenant-Id
    - X-Roles: comma-separated
    """
    claims = {}
    tok = _bearer_token(request)
    if tok:
        claims = _decode_jwt_claims_unverified(tok)
    principal = (
        request.headers.get("x-principal")
        or str(claims.get("sub") or claims.get("email") or "anonymous")
    )
    tenant_id = (
        request.headers.get("x-tenant-id")
        or str(claims.get("tenant_id") or claims.get("tid") or "default")
    )
    r_hdr = request.headers.get("x-roles", "")
    if r_hdr.strip():
        roles = tuple(x.strip() for x in r_hdr.split(",") if x.strip())
    else:
        rc = claims.get("roles") or claims.get("role")
        if isinstance(rc, list):
            roles = tuple(str(x).strip() for x in rc if str(x).strip())
        elif isinstance(rc, str) and rc.strip():
            roles = tuple(x.strip() for x in rc.split(",") if x.strip())
        else:
            # Backward-compatible default for local/dev without identity headers.
            roles = ("platform_admin",)
    return Principal(principal=principal, tenant_id=tenant_id, roles=roles)


def require_any_role(p: Principal, allowed: set[str]) -> None:
    if "platform_admin" in p.roles:
        return
    if any(r in allowed for r in p.roles):
        return
    raise HTTPException(status_code=403, detail="forbidden: role")


def require_tenant_match(p: Principal, namespace: str) -> None:
    if "platform_admin" in p.roles:
        return
    if not namespace:
        namespace = "default"
    if namespace != p.tenant_id:
        raise HTTPException(status_code=403, detail="forbidden: tenant namespace mismatch")


def _sensitive_get_path(path: str) -> bool:
    """GET/HEAD that expose rules, deployment, or governance need the key when set."""
    if path == "/system/deployment":
        return True
    if path.startswith("/governance/"):
        return True
    if path == "/rules" or path.startswith("/rules/"):
        return True
    return False


def install_optional_api_key_middleware(app: FastAPI) -> None:
    """If SPARKRULES_API_KEY is set, require it for mutating methods and sensitive GETs."""
    required = _env_api_key()
    if not required:
        return

    @app.middleware("http")
    async def _api_key_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        if request.method in ("GET", "HEAD"):
            if not _sensitive_get_path(request.url.path):
                return await call_next(request)
        if _supplied_key(request) != required:
            return JSONResponse(
                status_code=401, content={"detail": "invalid or missing API key"}
            )
        return await call_next(request)

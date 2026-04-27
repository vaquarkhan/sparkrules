from __future__ import annotations

import os
from typing import Awaitable, Callable

from fastapi import FastAPI
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

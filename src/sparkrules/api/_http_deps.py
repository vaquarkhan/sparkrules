"""FastAPI / Starlette imports with a clear error when the ``[api]`` extra is not installed."""

from __future__ import annotations

_MSG = "Install HTTP API dependencies with: pip install sparkrules[api]"

try:
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.responses import JSONResponse
    from starlette.staticfiles import StaticFiles
except ImportError as exc:  # pragma: no cover — CI always installs ``[api]``
    raise ImportError(_MSG) from exc

__all__ = [
    "FastAPI",
    "HTTPException",
    "JSONResponse",
    "Query",
    "Request",
    "StaticFiles",
]

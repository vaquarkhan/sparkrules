"""FastAPI / Starlette imports with a clear error when the ``[api]`` extra is not installed."""

from __future__ import annotations

_MSG = (
    "FastAPI/Starlette (and `uvicorn sparkrules.api.app:create_app`) require the optional "
    "HTTP stack. Install with: pip install 'sparkrules[api]' "
    "(or `pip install -e '.[api]'` from a source checkout)."
)

try:
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.responses import JSONResponse, Response
    from starlette.staticfiles import StaticFiles
except ImportError as exc:  # pragma: no cover — CI always installs ``[api]``
    raise ImportError(_MSG) from exc

__all__ = [
    "FastAPI",
    "HTTPException",
    "JSONResponse",
    "Query",
    "Request",
    "Response",
    "StaticFiles",
]

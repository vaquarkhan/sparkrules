"""Optional Workbench UI login (username/password + signed session token).

Enable with ``SPARKRULES_WORKBENCH_AUTH=1``. Set ``SPARKRULES_WORKBENCH_USER`` and
``SPARKRULES_WORKBENCH_PASSWORD`` in production. If ``WORKBENCH_PASSWORD`` is unset and
``DEFAULT_CREDENTIALS`` is not ``0``, the implicit dev password is ``admin`` (see
``workbench_expected_credentials()``).

API automation can bypass the Workbench gate with a valid ``SPARKRULES_API_KEY`` header when that
env var is set on the server.

Set ``SPARKRULES_DISABLE_WORKBENCH_GATE=1`` to skip the HTTP gate while keeping login endpoints
(use ``workbench_http_gate_active()`` in middleware).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

_TOKEN_TTL_SEC = 7 * 24 * 3600


def normalize_workbench_username(raw: str) -> str:
    """Strip whitespace, remove a single leading '=' (spreadsheet copy/paste), casefold for compare."""
    t = (raw or "").strip()
    if t.startswith("="):
        t = t[1:].strip()
    return t.casefold()


def workbench_auth_enabled() -> bool:
    v = (os.environ.get("SPARKRULES_WORKBENCH_AUTH", "") or "").strip().lower()
    return v in ("1", "true", "yes")


def workbench_http_gate_active() -> bool:
    """True when API requests must include X-Workbench-Token or X-API-Key (unless exempt).

    Workbench login can stay enabled (``SPARKRULES_WORKBENCH_AUTH``) while the HTTP gate is
    turned off for emergencies or local use by setting ``SPARKRULES_DISABLE_WORKBENCH_GATE=1``.
    """
    if (os.environ.get("SPARKRULES_DISABLE_WORKBENCH_GATE", "") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return False
    return workbench_auth_enabled()


def _secret() -> bytes:
    raw = (
        os.environ.get("SPARKRULES_WORKBENCH_SECRET", "").strip()
        or os.environ.get("SPARKRULES_API_KEY", "").strip()
        or "sparkrules-workbench-dev-secret-change-me"
    )
    return raw.encode("utf-8")


def workbench_expected_credentials() -> tuple[str, str]:
    """Return (user, password) for login; password may be empty if misconfigured.

    If ``SPARKRULES_WORKBENCH_PASSWORD`` is unset:
    - Explicit ``SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS=0|false|no`` → no default password (login disabled until a password is set).
    - Otherwise → dev default password ``admin`` (same as ``DEFAULT_CREDENTIALS=1``), so enabling only ``WORKBENCH_AUTH`` is enough for local tries.
    Production: set a strong ``SPARKRULES_WORKBENCH_PASSWORD`` or set ``DEFAULT_CREDENTIALS=0`` to block defaults.
    """
    user = (os.environ.get("SPARKRULES_WORKBENCH_USER", "") or "").strip() or "admin"
    pw = (os.environ.get("SPARKRULES_WORKBENCH_PASSWORD", "") or "").strip()
    if not pw:
        deny_def = (
            (os.environ.get("SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS", "") or "").strip().lower()
        )
        if deny_def in ("0", "false", "no"):
            return user, ""
        pw = "admin"
    return user, pw


def verify_credentials(username: str, password: str) -> bool:
    """Constant-time compare against configured Workbench credentials (username match is case-insensitive)."""
    u, p = workbench_expected_credentials()
    if not p:
        return False
    try:
        nu = normalize_workbench_username(username)
        ne = normalize_workbench_username(u)
        # Password: exact octets (case-sensitive), after UTF-8 strip only.
        pw = (password or "").strip()
        return hmac.compare_digest(nu.encode("utf-8"), ne.encode("utf-8")) and hmac.compare_digest(
            pw.encode("utf-8"), p.encode("utf-8")
        )
    except Exception:
        return False


def create_workbench_token(username: str) -> str:
    exp = int(time.time()) + _TOKEN_TTL_SEC
    payload = json.dumps({"u": username, "exp": exp}, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(_secret(), payload, hashlib.sha256).hexdigest()
    body = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{body}.{sig}"


def verify_workbench_token(token: str) -> str | None:
    """Return username if valid; else None."""
    if not token or "." not in token:
        return None
    try:
        body_b64, sig = token.rsplit(".", 1)
        pad = "=" * (-len(body_b64) % 4)
        payload = base64.urlsafe_b64decode((body_b64 + pad).encode("ascii"))
        expect = hmac.new(_secret(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect.encode("ascii"), sig.encode("ascii")):
            return None
        d: dict[str, Any] = json.loads(payload.decode("utf-8"))
        if int(d.get("exp", 0)) < int(time.time()):
            return None
        u = d.get("u")
        return str(u) if u else None
    except Exception:
        return None


def is_path_exempt_from_workbench_gate(path: str) -> bool:
    if path in ("/health", "/metrics", "/openapi.json", "/docs", "/redoc"):
        return True
    if path.startswith("/workbench"):
        return True
    if path.startswith("/api/workbench/auth"):
        return True
    return False

from __future__ import annotations

"""Ranger-compatible authorization for SparkRules call sites.

When ``SPARKRULES_RANGER_BASE_URL`` is set, decisions are delegated to
:func:`sparkrules.policy.ranger_client.query_ranger_allowed` (HTTP, fail-closed on errors).
Otherwise the legacy **local allow-list** behavior applies: deny empty principals; allow others
(suitable only for dev/test — use the HTTP path in production behind a real policy service).
"""

import os

from sparkrules.policy.ranger_client import RangerPolicyError, query_ranger_allowed


def ranger_allow_stub(
    *,
    user: str,
    resource_type: str,
    resource_name: str,
    action: str,
) -> bool:
    """Return True iff access is allowed (see module docstring for HTTP vs local modes)."""
    if not user.strip():
        return False
    base = (os.environ.get("SPARKRULES_RANGER_BASE_URL", "") or "").strip()
    if base:
        path = (os.environ.get("SPARKRULES_RANGER_EVAL_PATH", "") or "/ranger-compat/access-eval").strip()
        if not path.startswith("/"):
            path = "/" + path
        field = (os.environ.get("SPARKRULES_RANGER_RESULT_FIELD", "") or "isAllowed").strip() or "isAllowed"
        try:
            return query_ranger_allowed(
                base,
                user=user,
                resource_type=resource_type,
                resource_name=resource_name,
                action=action,
                evaluate_path=path,
                result_field=field,
            )
        except (RangerPolicyError, RuntimeError, OSError, TypeError, ValueError):
            return False
    return True

"""HTTP helper for Ranger-style access checks (policy-as-code in front of SparkRules).

Many deployments expose a small JSON endpoint (gateway in front of Apache Ranger) that
accepts ``user``, ``resource``, and ``accessType`` and returns a boolean ``isAllowed`` (or
a configurable field name). This module posts a minimal payload and reads that flag.

For full Ranger ``RangerAccessRequest`` payloads, pass ``extra_payload`` to merge fields,
or call Ranger directly from your integration layer.
"""

from __future__ import annotations

import json
from typing import Any, Mapping


class RangerPolicyError(RuntimeError):
    """Raised when the Ranger-compatible endpoint returns an error or an unusable body."""


def query_ranger_allowed(
    base_url: str,
    *,
    user: str,
    resource_type: str,
    resource_name: str,
    action: str,
    evaluate_path: str = "/ranger-compat/access-eval",
    result_field: str = "isAllowed",
    extra_payload: Mapping[str, Any] | None = None,
    timeout_seconds: float = 10.0,
) -> bool:
    """POST JSON to ``base_url + evaluate_path`` and return the boolean decision field.

    Default body shape::

        {
          "user": "<user>",
          "resource": {"type": "<resource_type>", "name": "<resource_name>"},
          "accessType": "<action>",
          ... optional merges from extra_payload ...
        }

    ``result_field`` names a top-level boolean in the JSON response (default ``isAllowed``).
    """
    try:
        import httpx
    except ImportError as e:
        raise RuntimeError(
            "Ranger HTTP client requires httpx (pip install sparkrules[api])",
        ) from e

    url = base_url.rstrip("/") + evaluate_path
    payload: dict[str, Any] = {
        "user": user,
        "resource": {"type": resource_type, "name": resource_name},
        "accessType": action,
    }
    if extra_payload:
        payload.update(dict(extra_payload))
    try:
        r = httpx.post(url, json=payload, timeout=timeout_seconds)
    except Exception as e:  # noqa: BLE001
        raise RangerPolicyError(str(e)) from e
    if r.status_code >= 400:
        raise RangerPolicyError(f"Ranger HTTP {r.status_code}: {r.text[:500]}")
    try:
        body = r.json()
    except json.JSONDecodeError as e:  # noqa: PERF203
        raise RangerPolicyError("Ranger response not JSON") from e
    if not isinstance(body, dict):
        raise RangerPolicyError("Ranger response must be a JSON object")
    if result_field not in body:
        raise RangerPolicyError(f"Ranger response missing field {result_field!r}")
    val = body[result_field]
    if not isinstance(val, bool):
        raise RangerPolicyError(
            f"Ranger field {result_field!r} must be boolean, got {type(val).__name__}"
        )
    return val

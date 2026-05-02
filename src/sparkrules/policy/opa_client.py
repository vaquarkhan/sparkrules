"""HTTP client helpers for evaluating OPA/Rego bundles (policy-as-code at runtime)."""

from __future__ import annotations

from typing import Any, Mapping


class OpaDecisionError(RuntimeError):
    pass


def query_opa(
    base_url: str,
    *,
    package_path: str,
    input_data: Mapping[str, Any],
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """POST to OPA ``/v1/data/<package.path>`` and return parsed JSON ``result``.

    ``base_url`` should be like ``http://localhost:8181`` without trailing slash.
    """
    import json

    url = base_url.rstrip("/") + "/v1/data/" + "/".join(package_path.strip(".").split("."))
    try:
        import httpx
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("OPA client requires httpx (pip install sparkrules[api])") from e
    try:
        r = httpx.post(
            url,
            json={"input": dict(input_data)},
            timeout=timeout_seconds,
        )
    except Exception as e:  # noqa: BLE001
        raise OpaDecisionError(str(e)) from e
    if r.status_code >= 400:
        raise OpaDecisionError(f"OPA HTTP {r.status_code}: {r.text[:500]}")
    try:
        body = r.json()
    except json.JSONDecodeError as e:  # noqa: PERF203
        raise OpaDecisionError("OPA response not JSON") from e
    result = body.get("result")
    if isinstance(result, dict):
        return result
    raise OpaDecisionError("OPA result missing or not an object")

"""OPA HTTP client and Ranger-compatible allow check (local vs HTTP modes).

- :func:`sparkrules.policy.opa_client.query_opa` posts to a running OPA ``/v1/data/...``
- :func:`sparkrules.policy.ranger_compat.ranger_allow_stub` delegates to Ranger when
  ``SPARKRULES_RANGER_BASE_URL`` is set; otherwise uses the dev allow-list stub.

  python examples/python/policy_opa_ranger_demo.py

Optional: start OPA on port 8181 with a bundle exposing ``package.sparkrules.allow``
and a rule ``allow { input.user == "alice" }``, then set::

    set SPARKRULES_OPA_URL=http://127.0.0.1:8181
"""

from __future__ import annotations

import os

from sparkrules.policy.opa_client import OpaDecisionError, query_opa
from sparkrules.policy.ranger_compat import ranger_allow_stub


def main() -> None:
    print(
        "Ranger stub (no SPARKRULES_RANGER_BASE_URL):",
        ranger_allow_stub(user="alice", resource_type="Rule", resource_name="r1", action="READ"),
    )

    base = (os.environ.get("SPARKRULES_OPA_URL") or "").strip()
    if not base:
        print(
            "OPA: skip live call (set SPARKRULES_OPA_URL, e.g. http://127.0.0.1:8181, "
            "and ensure package_path matches your Rego bundle).",
        )
        return
    try:
        out = query_opa(
            base,
            package_path="sparkrules.allow",
            input_data={"user": "alice"},
            timeout_seconds=3.0,
        )
        print("OPA result:", out)
    except OpaDecisionError as e:
        print("OPA call failed (expected if OPA is not running):", e)


if __name__ == "__main__":
    main()

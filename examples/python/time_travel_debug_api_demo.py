"""Capture a run to ``IcebergLikeTable`` storage and replay it (optionally with fact override).

Mirrors ``POST /debug/time-travel/capture`` and ``POST /debug/time-travel/replay``.

Requires ``pip install sparkrules[api]``.

  python examples/python/time_travel_debug_api_demo.py
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        print('Install: pip install "sparkrules[api]"', file=sys.stderr)
        return 1

    from sparkrules.api import AppDeps, create_app

    c = TestClient(create_app(AppDeps()))
    headers = {"X-Roles": "run_operator", "X-Tenant-Id": "default"}
    cap = c.post(
        "/debug/time-travel/capture",
        json={
            "run_id": "demo-run-1",
            "drl": 'rule "r" when $t : T ( $t.x > 1 ) then result.flag = true; end',
            "fact": {"t": {"x": 5}},
        },
        headers=headers,
    )
    cap.raise_for_status()
    snap = cap.json()["snapshot_id"]
    rep = c.post(
        "/debug/time-travel/replay",
        json={"snapshot_id": snap, "run_id": "demo-run-1", "fact_override": {"t": {"x": 0}}},
        headers=headers,
    )
    rep.raise_for_status()
    body = rep.json()
    print("replay fired=", body["fired"], "used_fact_override=", body["used_fact_override"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""KIE Server REST shim: deploy a container, run a stateless batch (migration smoke test).

Exercises the same routes as ``tests/unit/test_kie_api.py``:

- ``GET /kie-server/services/rest/server``
- ``PUT /kie-server/services/rest/server/containers/{id}``
- ``POST /kie-server/services/rest/server/containers/instances/{id}``

Requires ``pip install sparkrules[api]`` (FastAPI + TestClient).

  python examples/python/kie_rest_migration_recipe_demo.py
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        print('Install: pip install "sparkrules[api]"', file=sys.stderr)
        return 1

    from sparkrules.api import AppDeps, create_app
    from sparkrules.api.kie import reset_kie_containers_for_tests

    reset_kie_containers_for_tests()
    c = TestClient(create_app(AppDeps()))
    assert c.get("/kie-server/services/rest/server").json()["type"] == "SUCCESS"
    deploy = c.put(
        "/kie-server/services/rest/server/containers/demo",
        json={
            "drl": """
rule r when $person : Person ( true ) then
result.ok = true;
result.decision = "approve";
end
"""
        },
    )
    deploy.raise_for_status()
    exe = c.post(
        "/kie-server/services/rest/server/containers/instances/demo",
        json={
            "lookup": "defaultKieSession",
            "commands": [
                {"insert": {"object": {"com.demo.Person": {"score": 700}}}},
                {"fire-all-rules": {}},
            ],
        },
    )
    exe.raise_for_status()
    payload = exe.json()
    raw = payload["result"]
    inner = json.loads(raw) if isinstance(raw, str) else raw
    print("KIE migration smoke OK; decision=", inner.get("final-action", {}).get("decision"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

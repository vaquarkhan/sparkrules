"""Load the sparkrules FastAPI app in-process and print basic API metadata.

This avoids ``TestClient`` / httpx incompatibilities across tool versions. For
real HTTP, run uvicorn and open ``/docs`` (see [examples/README.md](../README.md)).

  python examples/python/api_inprocess.py
"""

from __future__ import annotations

from sre.api import AppDeps, create_app


def main() -> int:
    app = create_app(AppDeps())
    o = app.openapi()
    print("app", o["info"]["title"], o["info"]["version"])
    print("sample paths", sorted(o["paths"])[:8])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

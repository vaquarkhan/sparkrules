"""Start SparkRules API + Workbench. Same interpreter as: python scripts/dev_server.py"""
from __future__ import annotations

import os
import sys


def _main() -> None:
    port = int(os.environ.get("SPARKRULES_PORT", "8042"))
    try:
        import sre.api.app  # noqa: F401
    except ImportError as e:
        print(
            "ERROR: cannot import sre. From the repository root run:\n"
            f"  {sys.executable} -m pip install -e .\n"
            f"Import error: {e}",
            file=sys.stderr,
        )
        raise SystemExit(1) from e
    import uvicorn

    print("Python:     ", sys.executable)
    print("Python ver: ", sys.version.split()[0])
    print("Workbench:  ", f"http://127.0.0.1:{port}/workbench/")
    print("Health:     ", f"http://127.0.0.1:{port}/health")
    print("Stop:       Ctrl+C in this window.\n")
    uvicorn.run(
        "sre.api.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=port,
    )


if __name__ == "__main__":
    _main()

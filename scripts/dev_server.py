"""Start SparkRules API + Workbench. Same interpreter as: python scripts/dev_server.py

By default this **removes SPARKRULES_WORKBENCH_AUTH** for the child process so local
/workbench loads without session token or X-API-Key (shell profiles often set the variable).

Use ``--with-workbench-auth`` to keep your environment's workbench auth setting.
"""

from __future__ import annotations

import argparse
import os
import sys


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SparkRules API + Workbench (uvicorn).")
    parser.add_argument(
        "--with-workbench-auth",
        action="store_true",
        help="Keep SPARKRULES_WORKBENCH_AUTH from the environment (default: remove for open local UI).",
    )
    parser.add_argument(
        "--no-workbench-auth",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for console_scripts."""
    _main()


def _main() -> None:
    args = _parse_args()
    if args.with_workbench_auth:
        pass
    else:
        had = os.environ.pop("SPARKRULES_WORKBENCH_AUTH", None)
        if had is not None:
            print(
                "Note:       Removed SPARKRULES_WORKBENCH_AUTH for open local Workbench "
                "(stop 401 on /rules/*). Use --with-workbench-auth to keep your shell value."
            )

    port = int(os.environ.get("SPARKRULES_PORT", "8042"))
    try:
        import sparkrules.api.app  # noqa: F401
    except ImportError as e:
        print(
            "ERROR: cannot import sparkrules. From the repository root run:\n"
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
    wa = (os.environ.get("SPARKRULES_WORKBENCH_AUTH", "") or "").strip().lower()
    dg = (os.environ.get("SPARKRULES_DISABLE_WORKBENCH_GATE", "") or "").strip().lower()
    if wa in ("1", "true", "yes"):
        defc = (
            (os.environ.get("SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS", "") or "").strip().lower()
        )
        hint = (
            "Workbench login ON — use admin/admin if DEFAULT_CREDENTIALS=1 (see docs/WORKBENCH_LOGIN.md)"
            if defc in ("1", "true", "yes")
            else "Workbench login ON — set SPARKRULES_WORKBENCH_USER / SPARKRULES_WORKBENCH_PASSWORD"
        )
        print("Auth:       ", hint)
        if dg in ("1", "true", "yes"):
            print(
                "Gate:       ",
                "DISABLED (SPARKRULES_DISABLE_WORKBENCH_GATE — API open without token/key)",
            )
    else:
        print(
            "Auth:       ",
            "Workbench HTTP gate off (no SPARKRULES_WORKBENCH_AUTH in this process).",
        )
    print("Stop:       Ctrl+C in this window.\n")
    uvicorn.run(
        "sparkrules.api.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=port,
    )


if __name__ == "__main__":
    _main()

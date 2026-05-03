"""PostgreSQL-backed rule metadata store (requires a running server + URL).

Set ``DATABASE_URL`` (or pass ``--dsn``) to a Postgres connection string, e.g.::

    set DATABASE_URL=postgresql://user:pass@localhost:5432/mydb
    python examples/store/postgres_quickstart.py

Requires: ``pip install sparkrules[store]`` (installs psycopg).

If no URL is provided, this script prints setup hints and exits 0.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime

from sparkrules.model.rule import Rule, RuleDefinition, RuleFormat, new_rule_id
from sparkrules.store import create_rule_store


def _sample_rule(handle: str) -> Rule:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    return Rule(
        new_rule_id(),
        handle,
        0,
        "demo",
        0,
        t0,
        None,
        True,
        RuleDefinition(f'rule "{handle}" when $t : T ( true ) then end', RuleFormat.DRL),
        None,
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dsn", default=os.getenv("DATABASE_URL", ""), help="Postgres URL")
    args = p.parse_args()

    if not args.dsn.strip():
        print(__doc__)
        return 0

    try:
        import psycopg  # noqa: F401
    except ImportError:
        print("Install store extra: pip install sparkrules[store]", file=sys.stderr)
        return 1

    store = create_rule_store("postgres", database_url=args.dsn)
    r = store.insert(_sample_rule("pg-demo-rule"))
    got = store.get("pg-demo-rule", r.version)
    print(f"Inserted + read back: handle={got.rule_handle!r} version={got.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

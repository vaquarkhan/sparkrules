"""Minimal DuckDB-backed rule metadata store (file ``rules.duckdb`` in cwd).

Requires: ``pip install sparkrules[store]`` (installs DuckDB driver).

  python examples/store/duckdb_quickstart.py
"""

from __future__ import annotations

import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

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
    try:
        import duckdb  # noqa: F401
    except ImportError:
        print("Install store extra: pip install sparkrules[store]", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "rules.duckdb"
        store = create_rule_store("duckdb", db_path=str(db))
        r = store.insert(_sample_rule("demo-rule"))
        got = store.get("demo-rule", r.version)
        print(f"Inserted + read back: handle={got.rule_handle!r} version={got.version}")
        print(f"DuckDB file: {db} (deleted after demo exits)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

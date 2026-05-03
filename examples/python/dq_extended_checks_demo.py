"""Table-scoped DQ checks: uniqueness, regex, column sum, row count.

Extends :mod:`sparkrules.dq` beyond row-level ``ExpectNotNull`` / ``ExpectBetween``.

  python examples/python/dq_extended_checks_demo.py
"""

from __future__ import annotations

from sparkrules.dq import (
    DataQualityEngine,
    DqSeverity,
    ExpectColumnSumBetween,
    ExpectRegex,
    ExpectRowCountWithin,
    ExpectUnique,
)


def main() -> None:
    rows = [
        {"id": "a", "amt": 10, "email": "a@x.com"},
        {"id": "a", "amt": 20, "email": "b@x.com"},
        {"id": "c", "amt": 30, "email": "not-an-email"},
    ]
    checks = [
        ExpectUnique("id", tolerance=0.0),
        ExpectRegex("email", r".+@.+\..+", severity=DqSeverity.INFO),
        ExpectColumnSumBetween("amt", 0, 100),
        ExpectRowCountWithin(2, 3),
    ]
    engine = DataQualityEngine()
    print("Evaluating last row with full batch context (id / email / table aggregates):\n")
    violations = engine.evaluate(rows[2], checks, rows=rows)
    for v in violations:
        print(f"  [{v.severity.value}] {v.code}: {v.field} — {v.message}")
    if not violations:
        print("  (no violations)")


if __name__ == "__main__":
    main()

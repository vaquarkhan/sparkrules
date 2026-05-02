"""Data profiling and quality checks before rule evaluation.

Demonstrates:
- Statistical profiling (completeness, uniqueness, mean/stddev/percentiles)
- DQ checks (not-null, range, in-set)
- Profile-then-evaluate workflow

  python examples/python/data_profiling_demo.py
"""

from __future__ import annotations

import json

from sparkrules.dq import DataQualityEngine, ExpectNotNull, ExpectBetween, ExpectInSet
from sparkrules.dq.profile import profile_rows


def main() -> None:
    # Sample loan application data
    applications = [
        {"fico": 720, "income": 85000, "dti": 0.32, "state": "CA", "loan_amount": 350000},
        {"fico": 580, "income": 32000, "dti": 0.55, "state": "TX", "loan_amount": 150000},
        {"fico": None, "income": 55000, "dti": 0.38, "state": "NY", "loan_amount": 280000},
        {"fico": 650, "income": None, "dti": 0.41, "state": "FL", "loan_amount": 200000},
        {"fico": 780, "income": 120000, "dti": 0.22, "state": "WA", "loan_amount": 500000},
        {"fico": 690, "income": 48000, "dti": 0.45, "state": "CA", "loan_amount": 180000},
        {"fico": 710, "income": 67000, "dti": 0.35, "state": "TX", "loan_amount": 250000},
        {"fico": 620, "income": 38000, "dti": 0.50, "state": "NY", "loan_amount": 120000},
    ]

    # 1. Profile the data
    print("=== Data Profile ===")
    profile = profile_rows(applications)
    print(f"Rows: {profile.total_rows}, Fields: {profile.total_fields}\n")

    for f in profile.fields:
        line = f"  {f.field_name:15s} completeness={f.completeness:.0%}  unique={f.uniqueness:.0%}"
        if f.numeric_stats:
            ns = f.numeric_stats
            line += f"  mean={ns.mean:,.0f}  min={ns.min_val}  max={ns.max_val}  p50={ns.p50:,.0f}"
        if f.top_values:
            top = f.top_values[0]
            line += f"  top='{top[0]}'({top[1]})"
        print(line)

    # 2. Run DQ checks
    print("\n=== Data Quality Checks ===")
    dq = DataQualityEngine()
    checks = [
        ExpectNotNull(field="fico"),
        ExpectNotNull(field="income"),
        ExpectBetween(field="fico", min_value=300, max_value=850),
        ExpectBetween(field="dti", min_value=0, max_value=1.0),
        ExpectInSet(field="state", allowed_values=("CA", "TX", "NY", "FL", "WA", "OR")),
    ]

    total_violations = 0
    for app in applications:
        violations = dq.evaluate(app, checks)
        if violations:
            total_violations += len(violations)
            print(f"  Row (fico={app.get('fico')}): {len(violations)} violation(s)")
            for v in violations:
                print(f"    - [{v.severity.value}] {v.field}: {v.message}")

    if total_violations == 0:
        print("  All checks passed!")
    else:
        print(f"\n  Total violations: {total_violations}")

    # 3. Summary
    print("\n=== Summary ===")
    print(json.dumps(profile.to_dict(), indent=2, default=str))


if __name__ == "__main__":
    main()

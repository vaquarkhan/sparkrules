"""Adverse-action notice generation for ECOA/FCRA compliance.

Demonstrates how to collect reason codes from multiple rule evaluations
and format them into a regulatory-grade adverse-action notice.

  python examples/python/adverse_action_demo.py
"""

from __future__ import annotations

import json

from sparkrules.executor import RuleExecutor, build_adverse_action_notice

RULES = [
    (
        'rule "fico-low" reason_codes ["CR001"] when $a : App( $a.fico < 620 ) '
        'then result.d = "decline"; result.r = "Low FICO score"; end'
    ),
    (
        'rule "dti-high" reason_codes ["DTI001"] when $a : App( $a.dti > 0.43 ) '
        'then result.d = "decline"; result.r = "High debt-to-income ratio"; end'
    ),
    (
        'rule "income-low" reason_codes ["IN001"] when $a : App( $a.income < 30000 ) '
        'then result.d = "decline"; result.r = "Insufficient income"; end'
    ),
    (
        'rule "ltv-high" reason_codes ["LTV001"] when $a : App( $a.ltv > 0.95 ) '
        'then result.d = "decline"; result.r = "Loan-to-value ratio too high"; end'
    ),
    (
        'rule "employment-short" reason_codes ["EM001"] when $a : App( $a.emp_years < 1 ) '
        'then result.d = "refer"; result.r = "Short employment history"; end'
    ),
]


def main() -> None:
    executor = RuleExecutor()
    applicant = {"a": {"fico": 580, "dti": 0.52, "income": 28000, "ltv": 0.97, "emp_years": 0.5}}

    print("=== Applicant ===")
    print(json.dumps(applicant["a"], indent=2))

    print("\n=== Rule Evaluations ===")
    results = []
    for drl in RULES:
        result = executor.run(applicant, drl)
        results.append(result)
        if result.fired:
            print(f"  FIRED: {result.rule_handle} - codes: {list(result.reason_codes)}")

    print("\n=== Adverse Action Notice (ECOA/FCRA) ===")
    notice = build_adverse_action_notice(
        results,
        decision="DECLINE",
        fact_id="APP-2024-001",
        max_reasons=4,  # ECOA requires up to 4 principal reasons
    )
    print(json.dumps(notice.to_dict(), indent=2))

    print(
        f"\nPrincipal reasons ({len(notice.principal_reasons)} of {len(notice.all_reason_codes)} total):"
    )
    for code in notice.principal_reasons:
        print(f"  - {code}")


if __name__ == "__main__":
    main()

"""Compare two adverse-action contexts (explainability / what-if).

Uses :func:`sparkrules.compliance.adverse_action_counterfactual_summary` — distinct from
:func:`sparkrules.executor.build_adverse_action_notice` (rule-fire aggregation).

  python examples/python/adverse_action_counterfactual_demo.py
"""

from __future__ import annotations

import json

from sparkrules.compliance import (
    AdverseActionContext,
    Jurisdiction,
    adverse_action_counterfactual_summary,
)


def main() -> None:
    base = AdverseActionContext(
        applicant_reference="APP-1001",
        decision_date_iso="2026-05-01",
        primary_reason_codes=("CR001", "DTI001"),
        creditor_or_controller_name="Demo Bank",
    )
    counterfactual = AdverseActionContext(
        applicant_reference="APP-1001",
        decision_date_iso="2026-05-01",
        primary_reason_codes=("CR001",),
        creditor_or_controller_name="Demo Bank",
    )
    summary = adverse_action_counterfactual_summary(base, counterfactual, Jurisdiction.US_ECOA_FCRA)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

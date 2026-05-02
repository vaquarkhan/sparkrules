"""Adverse-action reason aggregation for regulatory compliance.

Collects reason codes from rule chain evaluations and formats them into
structured adverse-action notices suitable for ECOA/FCRA (US) and
GDPR Article 22 (EU) compliance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from sparkrules.executor.rule_executor import FactResult


@dataclass(frozen=True, slots=True)
class AdverseActionNotice:
    """Structured adverse-action notice for regulatory reporting."""

    decision: str
    principal_reasons: tuple[str, ...]
    all_reason_codes: tuple[str, ...]
    fact_id: str
    rules_evaluated: int
    rules_fired: int
    max_reasons: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "principal_reasons": list(self.principal_reasons),
            "all_reason_codes": list(self.all_reason_codes),
            "fact_id": self.fact_id,
            "rules_evaluated": self.rules_evaluated,
            "rules_fired": self.rules_fired,
            "max_reasons": self.max_reasons,
        }


def build_adverse_action_notice(
    results: Sequence[FactResult],
    *,
    decision: str = "decline",
    max_reasons: int = 4,
    fact_id: str = "0",
) -> AdverseActionNotice:
    """Aggregate reason codes from multiple rule evaluations into a single notice.

    ECOA/FCRA requires up to 4 principal reasons for adverse action.
    GDPR Article 22 requires meaningful information about the logic involved.

    Args:
        results: Sequence of FactResult from rule evaluations.
        decision: The adverse decision (e.g. "decline", "refer", "restrict").
        max_reasons: Maximum principal reasons to include (default 4 per ECOA).
        fact_id: Identifier for the fact/application being evaluated.

    Returns:
        AdverseActionNotice with deduplicated, priority-ordered reason codes.
    """
    all_codes: list[str] = []
    fired_count = 0
    seen: set[str] = set()

    for r in results:
        if r.fired:
            fired_count += 1
            for code in r.reason_codes:
                if code not in seen:
                    seen.add(code)
                    all_codes.append(code)

    principal = tuple(all_codes[:max_reasons])

    return AdverseActionNotice(
        decision=decision,
        principal_reasons=principal,
        all_reason_codes=tuple(all_codes),
        fact_id=fact_id,
        rules_evaluated=len(results),
        rules_fired=fired_count,
        max_reasons=max_reasons,
    )

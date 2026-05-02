"""Structured adverse-action / explanation-of-decision scaffolding (ECOA/FCRA/GDPR Art.22 templates)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Sequence


class Jurisdiction(Enum):
    US_ECOA_FCRA = auto()
    EU_GDPR_ART22 = auto()


@dataclass(frozen=True, slots=True)
class AdverseActionContext:
    """Minimal facts regulators expect on a denial / automated decision."""

    applicant_reference: str
    decision_date_iso: str
    primary_reason_codes: tuple[str, ...]
    creditor_or_controller_name: str = "Creditor"


def build_adverse_action_notice(
    ctx: AdverseActionContext,
    j: Jurisdiction,
    *,
    appendix_lines: Sequence[str] | None = None,
) -> str:
    """Return a structured plaintext notice template (not legal advice).

    Organizations must replace body copy with **counsel-approved** wording before production.
    Optional ``appendix_lines`` append institution-specific disclosures after the standard blocks.
    """
    lines: list[str] = []
    rc = ", ".join(ctx.primary_reason_codes) if ctx.primary_reason_codes else "(none provided)"
    if j == Jurisdiction.US_ECOA_FCRA:
        lines.append("ADVERSE ACTION NOTICE (ECOA / FCRA)")
        lines.append("— Template: obtain legal review before consumer use —")
        lines.append(f"Applicant / account: {ctx.applicant_reference}")
        lines.append(f"Date: {ctx.decision_date_iso}")
        lines.append(f"Creditor: {ctx.creditor_or_controller_name}")
        lines.append(f"Principal reason codes: {rc}")
        lines.append(
            "Under ECOA and FCRA, you generally have the right to a written statement of the "
            "specific reasons for an adverse action within applicable time limits, and to dispute "
            "inaccurate information in consumer reports. Insert your jurisdiction-specific deadlines, "
            "contacts, and disclosures here after counsel approval."
        )
    elif j == Jurisdiction.EU_GDPR_ART22:
        lines.append("AUTOMATED DECISION / ARTICLE 22 GDPR (INFORMATION NOTICE)")
        lines.append("— Template: obtain legal review before production —")
        lines.append(f"Data subject reference: {ctx.applicant_reference}")
        lines.append(f"Date: {ctx.decision_date_iso}")
        lines.append(f"Controller: {ctx.creditor_or_controller_name}")
        lines.append(f"Logic / reason codes recorded: {rc}")
        lines.append(
            "Under Article 22 GDPR, where a decision is based solely on automated processing with "
            "legal or similarly significant effects, data subjects have rights including human "
            "intervention, expression of their point of view, and contestation of the decision. "
            "Insert controller contact, retention, and appeal procedures here after counsel approval."
        )
    if appendix_lines:
        lines.append("")
        lines.extend(str(x) for x in appendix_lines if str(x).strip())
    return "\n".join(lines)


def adverse_action_record(
    ctx: AdverseActionContext,
    j: Jurisdiction,
    *,
    appendix_lines: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Structured record (JSON-friendly) alongside :func:`build_adverse_action_notice` text."""
    return {
        "jurisdiction": j.name,
        "applicant_reference": ctx.applicant_reference,
        "decision_date_iso": ctx.decision_date_iso,
        "reason_codes": list(ctx.primary_reason_codes),
        "creditor_or_controller_name": ctx.creditor_or_controller_name,
        "notice_text": build_adverse_action_notice(ctx, j, appendix_lines=appendix_lines),
    }


def adverse_action_counterfactual_summary(
    base: AdverseActionContext,
    counterfactual: AdverseActionContext,
    j: Jurisdiction,
    *,
    appendix_lines: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Compare two fact snapshots under the same jurisdiction (explainability aid, not legal advice)."""
    base_rc = frozenset(base.primary_reason_codes)
    cf_rc = frozenset(counterfactual.primary_reason_codes)
    br = adverse_action_record(base, j, appendix_lines=appendix_lines)
    cr = adverse_action_record(counterfactual, j, appendix_lines=appendix_lines)
    return {
        "jurisdiction": j.name,
        "base": br,
        "counterfactual": cr,
        "reason_codes_added": sorted(cf_rc - base_rc),
        "reason_codes_removed": sorted(base_rc - cf_rc),
        "notices_differ": br["notice_text"] != cr["notice_text"],
    }

from __future__ import annotations

from dataclasses import dataclass

from sparkrules.model.rule_template import RuleTemplate


@dataclass(frozen=True, slots=True)
class GuidedField:
    name: str
    label: str
    required: bool
    kind: str


def guided_fields_from_template(template: RuleTemplate) -> list[GuidedField]:
    return [
        GuidedField(name=n, label=n.replace("_", " ").title(), required=True, kind="string")
        for n in sorted(template.placeholders)
    ]

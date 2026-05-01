from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Mapping

from sparkrules.parser.ast import RuleAst

if TYPE_CHECKING:
    from sparkrules.parser.parser import DrlParser


@dataclass(frozen=True, slots=True)
class RuleTemplate:
    name: str
    pattern: str
    placeholders: frozenset[str]
    _slot_re: ClassVar[re.Pattern[str]] = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

    @classmethod
    def from_pattern(cls, name: str, pattern: str) -> RuleTemplate:
        return cls(name=name, pattern=pattern, placeholders=frozenset(_extract_slots(pattern)))


def _extract_slots(pattern: str) -> frozenset[str]:
    return frozenset(RuleTemplate._slot_re.findall(pattern))


class MissingPlaceholderError(ValueError):
    pass


class ExtraPlaceholderError(ValueError):
    pass


def _substitute(pattern: str, values: Mapping[str, str], declared: frozenset[str]) -> str:
    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in values:
            raise MissingPlaceholderError(key)
        return values[key]

    for k in values:
        if k not in declared:
            raise ExtraPlaceholderError(k)
    return RuleTemplate._slot_re.sub(repl, pattern)


def ast_from_template(
    template: RuleTemplate, values: Mapping[str, str], *, _parser: DrlParser | None = None
) -> RuleAst:  # noqa: E501
    declared = template.placeholders
    for k in values:
        if k not in declared:
            raise ExtraPlaceholderError(k)
    for p in template.placeholders:
        if p not in values:
            raise MissingPlaceholderError(p)
    source = _substitute(template.pattern, values, declared)
    if _parser is None:
        from sparkrules.parser.parser import DrlParser

        p = DrlParser()
    else:
        p = _parser
    return p.parse(source)

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

from sparkrules.parser import parse
from sparkrules.parser.ast import RuleAst


class Strategy(enum.Enum):
    PUSHDOWN = 0
    DATAFRAME = 1
    BROADCAST = 2
    SQL_JOIN = 3


@dataclass
class StrategyClassifier:
    def classify(self, rule_src: str) -> Strategy:
        r = parse(rule_src)
        return self._classify_ast(r)

    def _classify_ast(self, r: RuleAst) -> Strategy:
        n_pats = len(r.when)
        if n_pats > 1:
            return Strategy.SQL_JOIN
        if n_pats and r.then:
            c = r.when[0].constraint
            if c is not None and self._is_simple(c):
                return Strategy.DATAFRAME
        return Strategy.BROADCAST

    def _is_simple(self, c: Any) -> bool:  # noqa: ANN401
        return True



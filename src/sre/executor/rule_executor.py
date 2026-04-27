from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping

from sre.compiler import evaluate_rule
from sre.parser import parse


@dataclass(frozen=True, slots=True)
class FactResult:
    fact_id: str
    rule_id: str
    rule_handle: str
    version: int
    pass_: str
    fired: bool
    reason_codes: tuple[str, ...]
    bound_fields: dict[str, Any]
    action_output: dict[str, Any]
    error_class: str | None
    error_message: str | None


class RuleExecutor:
    def run(
        self,
        fact: MutableMapping[str, Any],
        drl: str,
        *,
        fact_id: str = "0",
        rule_id: str = "r1",
        handle: str = "r1",
        version: int = 1,
        pass_: str = "SINGLE",
        allow_sql_join: bool = False,
    ) -> FactResult:
        r = parse(drl)
        if len(r.when) > 1 and not allow_sql_join:
            return FactResult(
                fact_id,
                rule_id,
                handle,
                version,
                pass_,
                False,
                (),
                {k: v for k, v in fact.items() if k != "result"},
                {},
                "SqlJoinNotImplemented",
                "join rules require Spark",
            )
        try:
            m = evaluate_rule(r, fact)
        except Exception as e:  # noqa: BLE001
            return FactResult(
                fact_id,
                rule_id,
                handle,
                version,
                pass_,
                False,
                (),
                {k: v for k, v in fact.items() if k != "result"},
                {},
                type(e).__name__,
                str(e),
            )
        if not m.fired:
            return FactResult(
                fact_id,
                rule_id,
                handle,
                version,
                pass_,
                False,
                r.reason_codes,
                m.bound,
                {},
                None,
                None,
            )
        return FactResult(
            fact_id,
            rule_id,
            handle,
            version,
            pass_,
            True,
            r.reason_codes,
            m.bound,
            m.action_output,
            None,
            None,
        )

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any, MutableMapping

from sparkrules.compiler import evaluate_rule
from sparkrules.parser import parse


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
    def _candidate_facts(
        self,
        base_fact: MutableMapping[str, Any],
        bind_names: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        # Local fallback for multi-pattern joins: if bind inputs are lists,
        # evaluate a Cartesian product of rows for those bindings.
        pools: list[list[Any]] = []
        for b in bind_names:
            v = base_fact.get(b)
            if isinstance(v, list):
                pools.append(list(v))
            else:
                pools.append([v])
        out: list[dict[str, Any]] = []
        for combo in product(*pools):
            row = dict(base_fact)
            for i, b in enumerate(bind_names):
                row[b] = combo[i]
            out.append(row)
        return out

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
            if len(r.when) > 1 and allow_sql_join:
                bind_names = tuple(p.bind_name for p in r.when)
                m = None
                for cand in self._candidate_facts(fact, bind_names):
                    mm = evaluate_rule(r, cand)
                    if mm.fired:
                        m = mm
                        break
                if m is None:
                    m = evaluate_rule(r, fact)
            else:
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

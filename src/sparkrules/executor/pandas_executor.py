"""Pandas batch evaluation for LocalRuleExecutor (Requirement 22).

Evaluates rules against a pandas DataFrame using vectorized operations
for simple rules and row-wise closure application for complex rules.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from sparkrules.compiler.closure import compile_action, compile_predicate
from sparkrules.compiler.rulepack import RulePack, Strategy
from sparkrules.runtime.engine_metrics import record_score_completed


def _safe_col(name: str) -> str:
    return name.replace("-", "_").replace(" ", "_").replace('"', "")


def apply_pandas(
    pack: RulePack,
    df: Any,
) -> Any:
    """Evaluate rules against a pandas DataFrame (Req 22).

    SQL_PUSHDOWN rules use pandas.eval() for vectorized evaluation.
    Other rules use row-wise closure application.

    Args:
        pack: A compiled RulePack.
        df: A pandas DataFrame with fact columns.

    Returns:
        pandas DataFrame with r_<rule> boolean columns, action_<field>
        typed columns, and fired_any boolean column.
    """
    t0 = time.perf_counter()
    result = df.copy()

    # Pre-compile action closures
    action_closures: dict[str, list[tuple[str, Any]]] = {}
    for rule in pack.rules:
        fns = []
        for action in rule.ast.then:
            fname, fn = compile_action(action)
            fns.append((fname, fn))
        action_closures[rule.name] = fns

    # Evaluate each rule
    for rule in pack.rules:
        col_name = f"r_{_safe_col(rule.name)}"

        if rule.strategy == Strategy.SQL_PUSHDOWN and rule.predicate_sql:
            # Vectorized: try pandas.eval (Req 22, AC 1)
            try:
                pandas_expr = _spark_sql_to_pandas(rule.predicate_sql)
                result[col_name] = result.eval(pandas_expr)
            except Exception:  # noqa: BLE001
                # Fall back to row-wise
                pred_fn = compile_predicate(rule.ast.when[0].constraint)
                result[col_name] = result.apply(lambda row, _fn=pred_fn: _fn(row.to_dict()), axis=1)
        else:
            # Row-wise closure application (Req 22, AC 2)
            pred_fn = compile_predicate(rule.ast.when[0].constraint)
            result[col_name] = result.apply(lambda row, _fn=pred_fn: _fn(row.to_dict()), axis=1)

        # Action columns
        for fname, fn in action_closures.get(rule.name, []):
            action_col = f"action_{_safe_col(fname)}"
            if action_col not in result.columns:
                result[action_col] = None
            mask = result[col_name]
            if mask.any():
                result.loc[mask, action_col] = result.loc[mask].apply(
                    lambda row, _fn=fn: _fn(row.to_dict()), axis=1
                )

    # fired_any column (Req 22, AC 3)
    rule_cols = [
        f"r_{_safe_col(r.name)}" for r in pack.rules if f"r_{_safe_col(r.name)}" in result.columns
    ]
    if rule_cols:
        result["fired_any"] = result[rule_cols].any(axis=1)
    else:
        result["fired_any"] = False

    elapsed = time.perf_counter() - t0
    fires_by_strategy: dict[str, int] = {}
    for rule in pack.rules:
        col_name = f"r_{_safe_col(rule.name)}"
        n = int(result[col_name].fillna(False).astype(bool).sum())
        if n:
            strat = rule.strategy.name
            fires_by_strategy[strat] = fires_by_strategy.get(strat, 0) + n

    record_score_completed(
        latency_seconds=elapsed,
        rows=len(result),
        pack=pack,
        executor_tag="v2_pandas",
        fires_by_strategy=fires_by_strategy,
    )

    return result


def _transform_spark_sql_outside_string_literals(
    sql: str, transform_chunk: Callable[[str], str]
) -> str:
    """Apply *transform_chunk* only outside single-quoted literals (``''`` escaped)."""

    out: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        c = sql[i]
        if c == "'":
            out.append("'")
            i += 1
            while i < n:
                if sql[i] == "'":
                    out.append("'")
                    i += 1
                    if i < n and sql[i] == "'":
                        out.append("'")
                        i += 1
                        continue
                    break
                out.append(sql[i])
                i += 1
            continue
        start = i
        while i < n and sql[i] != "'":
            i += 1
        out.append(transform_chunk(sql[start:i]))
    return "".join(out)


def _spark_sql_to_pandas(sql: str) -> str:
    """Adapt Spark SQL expression to pandas.eval() syntax.

    Handles basic transformations:
    - Spark = to pandas ==
    - Spark AND/OR to pandas &/|
    - Spark NOT to pandas ~
    - Operators are rewritten only outside string literals (avoids mangling ``'a AND b'``).
    """

    def _chunk(expr: str) -> str:
        e = expr.replace(" = ", " == ").replace("(= ", "(== ")
        e = e.replace(" AND ", " & ").replace(" OR ", " | ")
        e = e.replace("(NOT ", "(~").replace("NOT ", "~")
        return e

    expr = _transform_spark_sql_outside_string_literals(sql.strip(), _chunk)
    # RLIKE not supported in pandas.eval - will fall back to closure
    if "RLIKE" in expr or "array_contains" in expr or "CONTAINS" in expr:
        raise ValueError("pandas.eval does not support RLIKE/array_contains")
    return expr

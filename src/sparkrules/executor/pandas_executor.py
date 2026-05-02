"""Pandas batch evaluation for LocalRuleExecutor (Requirement 22).

Evaluates rules against a pandas DataFrame using vectorized operations
for simple rules and row-wise closure application for complex rules.
"""

from __future__ import annotations

from typing import Any

from sparkrules.compiler.alpha_network import AlphaNetwork
from sparkrules.compiler.closure import compile_action, compile_predicate
from sparkrules.compiler.rulepack import RulePack, Strategy
from sparkrules.compiler.translator import translate_predicate


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
    import pandas as pd

    result = df.copy()

    # Build alpha network for closure-based rules
    asts = [r.ast for r in pack.rules]
    net = AlphaNetwork.from_rules(asts)

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
                result[col_name] = result.apply(
                    lambda row, _fn=pred_fn: _fn(row.to_dict()), axis=1
                )
        else:
            # Row-wise closure application (Req 22, AC 2)
            pred_fn = compile_predicate(rule.ast.when[0].constraint)
            result[col_name] = result.apply(
                lambda row, _fn=pred_fn: _fn(row.to_dict()), axis=1
            )

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
    rule_cols = [f"r_{_safe_col(r.name)}" for r in pack.rules if f"r_{_safe_col(r.name)}" in result.columns]
    if rule_cols:
        result["fired_any"] = result[rule_cols].any(axis=1)
    else:
        result["fired_any"] = False

    return result


def _spark_sql_to_pandas(sql: str) -> str:
    """Adapt Spark SQL expression to pandas.eval() syntax.

    Handles basic transformations:
    - Spark = to pandas ==
    - Spark AND/OR to pandas &/|
    - Spark NOT to pandas ~
    - Strip outer parens for simple expressions
    """
    expr = sql.strip()
    # Spark uses = for equality, pandas uses ==
    # But our translator already uses = not ==, so convert
    expr = expr.replace(" = ", " == ").replace("(= ", "(== ")
    # AND/OR/NOT
    expr = expr.replace(" AND ", " & ").replace(" OR ", " | ")
    expr = expr.replace("(NOT ", "(~")
    expr = expr.replace("NOT ", "~")
    # RLIKE not supported in pandas.eval - will fall back to closure
    if "RLIKE" in expr or "array_contains" in expr or "CONTAINS" in expr:
        raise ValueError("pandas.eval does not support RLIKE/array_contains")
    return expr

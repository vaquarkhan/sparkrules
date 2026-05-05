"""Rule evaluation on PySpark DataFrames (parse once per partition, evaluate per row)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "apply_drl",
    "iter_rule_rows",
    "rows_from_session",
]


@runtime_checkable
class _RowLike(Protocol):
    def asDict(self) -> dict[str, Any]: ...


def iter_rule_rows(
    part: Iterator[Any],
    drl: str,
    *,
    fact_id_field: str = "id",
    use_v2: bool = True,
) -> Iterator[tuple[str, bool, str]]:
    """Map each Spark-like row to ``(fact_id, fired, out_json)`` (unit-testable, no Spark).

    When use_v2=True (default), uses compiled closures and alpha network
    for faster evaluation (Req 19). When False, uses the original AST-walking path.
    """
    from sparkrules.parser import parse_rules

    rules = parse_rules(drl)
    if len(rules) == 0:
        raise ValueError("DRL must contain at least one rule block")

    if use_v2:
        # V2 path: compiled closures + alpha network (Req 19)
        from sparkrules.compiler.alpha_network import AlphaNetwork
        from sparkrules.compiler.closure import compile_action

        net = AlphaNetwork.from_rules(rules)
        action_fns: dict[str, list[tuple[str, Any]]] = {}
        for rule in rules:
            fns = []
            for action in rule.then:
                fname, fn = compile_action(action)
                fns.append((fname, fn))
            action_fns[rule.name] = fns

        for row in part:
            if isinstance(row, dict):
                dct = row
            elif hasattr(row, "asDict") and callable(getattr(row, "asDict")):
                try:
                    dct = row.asDict(recursive=True)
                except TypeError:
                    dct = row.asDict()
            else:
                dct = dict(row)
            fact = {k: v for k, v in dct.items() if k != fact_id_field}
            fired_map = net.evaluate(fact)
            any_fired = False
            action_out: dict[str, Any] = {}
            bound: dict[str, Any] = dict(fact)
            for rule in rules:
                if fired_map.get(rule.name, False):
                    any_fired = True
                    for fname, fn in action_fns.get(rule.name, []):
                        if fname not in action_out:
                            try:
                                action_out[fname] = fn(fact)
                            except Exception:  # noqa: BLE001
                                action_out[fname] = None
            out = {"action": action_out, "bound": bound}
            yield str(dct.get(fact_id_field, "")), any_fired, json.dumps(out)
    else:
        # V1 legacy path: AST walking
        yield from _iter_rule_rows_v1(part, drl, fact_id_field=fact_id_field)


def _iter_rule_rows_v1(
    part: Iterator[Any],
    drl: str,
    *,
    fact_id_field: str = "id",
) -> Iterator[tuple[str, bool, str]]:
    from sparkrules.compiler import RuleMatch, evaluate_rule
    from sparkrules.compiler.discrimination import DiscriminationNetwork
    from sparkrules.parser import parse_rules
    from sparkrules.runtime.rule_chain import ChainExecutionPolicy, run_rule_chain

    rules = parse_rules(drl)
    if len(rules) == 1:
        ast = rules[0]
    else:

        def _eval_with_chain(facts: dict[str, Any]) -> RuleMatch:
            dn = DiscriminationNetwork.from_asts(rules)
            cr = run_rule_chain(
                rules,
                facts,
                ChainExecutionPolicy(stop_on_decline=False),
                discrimination=dn,
            )
            fired = any(step.fired for step in cr.steps)
            return RuleMatch(
                "__chain__",
                fired,
                dict(cr.final_bound),
                dict(cr.final_action),
            )

        ast = None
    for row in part:
        if isinstance(row, dict):
            dct = row
        elif hasattr(row, "asDict") and callable(getattr(row, "asDict")):
            try:
                dct = row.asDict(recursive=True)
            except TypeError:
                dct = row.asDict()
        else:
            dct = dict(row)
        fact = {k: v for k, v in dct.items() if k != fact_id_field}
        if ast is None:
            m2 = _eval_with_chain(fact)
        else:
            m2 = evaluate_rule(ast, fact)
        out = {"action": m2.action_output, "bound": m2.bound}
        yield str(dct.get(fact_id_field, "")), m2.fired, json.dumps(out)


def mpartition_rows(
    part: Any,
    drl_source: str,
    *,
    fact_id_field: str = "id",
) -> Any:
    """Map one partition; yields PySpark ``Row`` objects (import PySpark on use)."""
    from pyspark.sql import Row

    for t in iter_rule_rows(iter(part), drl_source, fact_id_field=fact_id_field):
        yield Row(t[0], t[1], t[2])


def apply_drl(
    df: Any,
    drl: str,
    *,
    fact_id_field: str = "id",
    use_v2: bool = True,
    output_format: str = "wide",
) -> Any:
    """Apply DRL rules to a Spark DataFrame.

    Args:
        df: Input Spark DataFrame with fact columns.
        drl: DRL rule text (one or more rules).
        fact_id_field: Column name for fact ID (used in v1 path).
        use_v2: If True (default), use the optimized V2 executor with
                Strategy A/B/C dispatch. If False, use the original
                mapPartitions path.
        output_format: For V2, ``"wide"`` (default) or ``"narrow"`` (see
            :class:`sparkrules.spark.executor.SparkRuleExecutor`).

    Returns:
        DataFrame with rule results. V2 path returns typed columns;
        V1 path returns (fact_id, fired, out_json).
    """
    if use_v2:
        from sparkrules.spark.executor import SparkRuleExecutor

        executor = SparkRuleExecutor.from_drl(drl)
        return executor.apply(df, output_format=output_format)

    # V1 legacy path
    return _apply_drl_v1(df, drl, fact_id_field=fact_id_field)


def _apply_drl_v1(df: Any, drl: str, *, fact_id_field: str = "id") -> Any:
    from pyspark.sql.types import (
        BooleanType,
        StringType,
        StructField,
        StructType,
    )

    spark = df.sparkSession
    sc = spark.sparkContext
    b = sc.broadcast(drl)
    fid = fact_id_field
    out_schema = StructType(
        [
            StructField("fact_id", StringType(), True),
            StructField("fired", BooleanType(), True),
            StructField("out_json", StringType(), True),
        ]
    )
    bval = b.value

    def mpart(part: Any) -> Any:
        yield from mpartition_rows(part, bval, fact_id_field=fid)

    r2 = df.rdd.mapPartitions(mpart)
    return spark.createDataFrame(r2, out_schema)


def rows_from_session(spark: Any, rows: list[dict]) -> Any:
    if not rows:
        from pyspark.sql.types import StringType, StructField, StructType

        s = StructType(
            [StructField("id", StringType(), True), StructField("n", StringType(), True)]
        )
        return spark.createDataFrame([], s)
    return spark.createDataFrame(rows)

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
) -> Iterator[tuple[str, bool, str]]:
    """Map each Spark-like row to ``(fact_id, fired, out_json)`` (unit-testable, no Spark)."""
    from sre.compiler import RuleMatch, evaluate_rule
    from sre.parser import parse_rules
    from sre.runtime.rule_chain import ChainExecutionPolicy, run_rule_chain

    rules = parse_rules(drl)
    if len(rules) == 0:
        raise ValueError("DRL must contain at least one rule block")
    if len(rules) == 1:
        ast = rules[0]
    else:

        def _eval_with_chain(facts: dict[str, Any]) -> RuleMatch:
            cr = run_rule_chain(
                rules,
                facts,
                ChainExecutionPolicy(stop_on_decline=False),
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
                dct = row.asDict(recursive=True)  # type: ignore[union-attr]
            except TypeError:
                dct = row.asDict()  # type: ignore[union-attr]; mocks without recursive=
        else:
            dct = dict(row)  # type: ignore[call-overload,arg-type]
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
) -> Any:
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

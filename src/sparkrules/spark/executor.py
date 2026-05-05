"""SparkRuleExecutor - V2 optimized Spark execution (Requirements 6-8, 10, 15-17, 20, 24).

Dispatches classified rules to three strategies:
- Strategy A (SQL_PUSHDOWN): F.expr() / F.when() - Catalyst-optimized, zero Python workers
- Strategy B (ALPHA_SHARED): shared alpha boolean columns + AND-reduction
- Strategy C (PYTHON_FALLBACK): mapPartitions with broadcast alpha network

Cross-path equivalence with LocalRuleExecutor is a hard requirement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sparkrules.compiler.alpha_network import AlphaNetwork
from sparkrules.compiler.rulepack import ClassifiedRule, RulePack
from sparkrules.compiler.translator import translate_predicate


class SchemaValidationError(TypeError):
    """Raised when facts DataFrame has MapType where StructType is expected (Req 15)."""

    pass


_SAFE_SPARK_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _common_coalesce_sql_type(dtypes: list[Any]) -> str:
    """Spark SQL type name so every branch of ``coalesce`` shares one Catalyst type (Req 17).

    Without a uniform cast, mixed Strategy A/B numeric literals vs Strategy C string
    staging columns can make ``coalesce`` fail type widening.
    """

    from pyspark.sql.types import (
        BooleanType,
        ByteType,
        DateType,
        DecimalType,
        DoubleType,
        FloatType,
        IntegerType,
        LongType,
        ShortType,
        StringType,
        TimestampType,
    )

    if not dtypes:
        return "string"

    def category(dt: Any) -> str:
        if isinstance(dt, BooleanType):
            return "bool"
        if isinstance(dt, (ByteType, ShortType, IntegerType, LongType)):
            return "integral"
        if isinstance(dt, (FloatType, DoubleType, DecimalType)):
            return "fractional"
        if isinstance(dt, StringType):
            return "str"
        if isinstance(dt, (TimestampType, DateType)):
            return "temporal"
        return "other"

    cats = {category(d) for d in dtypes}
    if len(cats) > 1:
        return "string"
    only = next(iter(cats))
    if only == "bool":
        return "boolean"
    if only == "integral":
        return "bigint"
    if only == "fractional":
        return "double"
    if only == "str":
        return "string"
    if only == "temporal":
        if len({type(d).__name__ for d in dtypes}) > 1:
            return "string"
        if isinstance(dtypes[0], TimestampType):
            return "timestamp"
        return "date"
    return "string"


def _staging_dtypes_for_merge(df: Any, salience_cols: list[tuple[int, str, int, str]]) -> list[Any]:
    """Collect non-null Spark data types for staging columns present on ``df``."""

    from pyspark.sql.types import NullType

    by_name = {f.name: f.dataType for f in df.schema.fields}
    out: list[Any] = []
    for t in salience_cols:
        col = t[-1]
        dt = by_name.get(col)
        if dt is not None and not isinstance(dt, NullType):
            out.append(dt)
    return out


def _safe_rule_col(name: str) -> str:
    """Sanitize rule name for use as a Spark column name."""
    return "r_" + name.replace("-", "_").replace(" ", "_").replace('"', "")


def _safe_action_col(field_name: str) -> str:
    return "action_" + field_name.replace("-", "_").replace(" ", "_")


def _staging_action_flat(salience: int, source_order: int, action_field: str) -> str:
    """Intermediate action column unique per rule (Req 17: salience + parse-order ties)."""

    return _safe_action_col(action_field) + "__s" + str(salience) + "_o" + str(source_order)


def _staging_action_column(rule: ClassifiedRule, action_field: str) -> str:
    return _staging_action_flat(rule.salience, rule.source_order, action_field)


def _action_fields_from_ast(rule: ClassifiedRule) -> list[str]:
    """Staging column names derive from RHS actions (Strategy C lacks ``action_sql``)."""

    return [action.field_path.replace("result.", "") for action in rule.ast.then]


def action_staging_merge_plan(
    pack: RulePack, *, df_columns: frozenset[str]
) -> dict[str, list[tuple[int, str, int, str]]]:
    """Salience-sorted staging columns per merged ``action_<field>`` (Req 17), without Spark calls.

    Each value list item is ``(salience, rule_name, source_order, staging_col_name)``.
    """

    action_fields: dict[str, list[tuple[int, str, int, str]]] = {}
    for rule in pack.rules:
        for action_field in _action_fields_from_ast(rule):
            col_name = _staging_action_column(rule, action_field)
            if col_name in df_columns:
                if action_field not in action_fields:
                    action_fields[action_field] = []
                action_fields[action_field].append(
                    (rule.salience, rule.name, rule.source_order, col_name),
                )
    for salience_cols in action_fields.values():
        salience_cols.sort(key=lambda x: (-x[0], x[1], x[2]))
    return action_fields


def _assert_machine_generated_alias(alias: str) -> None:
    if not _SAFE_SPARK_IDENTIFIER.fullmatch(alias):
        raise SchemaValidationError(
            f"Rule-derived Spark identifier '{alias}' is unsafe after sanitization (Req 33)."
        )


@dataclass
class SparkRuleExecutor:
    """V2 Spark executor with three-strategy dispatch (Req 6-8)."""

    rulepack: RulePack
    _drl: str = ""
    # Reused across apply() calls; cleared in refresh_rules (Strategy B planning).
    _alpha_net_plan: AlphaNetwork | None = field(default=None, init=False, repr=False)

    @staticmethod
    def from_drl(drl: str) -> SparkRuleExecutor:
        pack = RulePack.from_drl(drl)
        return SparkRuleExecutor(rulepack=pack, _drl=drl)

    def apply(self, df: Any, *, output_format: str = "wide") -> Any:
        """Execute all rules against a Spark DataFrame.

        Returns DataFrame with: original columns + r_<rule> booleans +
        action_<field> typed columns + fired_any boolean (``wide``), or a **narrow** projection
        with ``fired_rules``, ``actions`` (struct), and ``fired_any`` when ``output_format="narrow"``.
        """
        from pyspark.sql import functions as F
        from pyspark.sql.types import MapType

        if output_format not in ("wide", "narrow"):
            raise ValueError("output_format must be 'wide' or 'narrow'")

        # Req 15: Schema validation
        for col_field in df.schema:
            if isinstance(col_field.dataType, MapType):
                raise SchemaValidationError(
                    f"Column '{col_field.name}' has MapType but rules expect StructType. "
                    f"Use explicit schema: spark.createDataFrame(data, schema=StructType([...]))"
                )

        for rule in self.rulepack.rules:
            _assert_machine_generated_alias(_safe_rule_col(rule.name))

        result = df

        # Strategy A: SQL_PUSHDOWN (Req 6)
        result = self._apply_strategy_a(result)

        # Strategy B: ALPHA_SHARED (Req 7)
        result = self._apply_strategy_b(result)

        # Strategy C: PYTHON_FALLBACK (Req 8)
        result = self._apply_strategy_c(result)

        # Req 17: Cross-strategy salience resolution
        result = self._merge_actions(result)

        # fired_any column (Req 10): Spark greatest() requires ≥2 expressions.
        rule_cols = [_safe_rule_col(r.name) for r in self.rulepack.rules]
        present = [c for c in rule_cols if c in result.columns]
        if len(present) <= 1:
            if not present:
                result = result.withColumn("fired_any", F.lit(False))
            else:
                result = result.withColumn("fired_any", F.col(present[0]))
        else:
            result = result.withColumn(
                "fired_any",
                F.greatest(*[F.col(c) for c in present]),
            )

        if output_format == "narrow":
            return self._to_narrow_output(result)
        return result

    def apply_with_counts(
        self, df: Any, *, output_format: str = "wide"
    ) -> tuple[Any, dict[str, int]]:
        """Run :meth:`apply` and return one aggregate row of per-rule fire counts (avoids N scans)."""
        from pyspark.sql import functions as F

        result = self.apply(df, output_format=output_format)
        rule_cols = [_safe_rule_col(r.name) for r in self.rulepack.rules]
        present = [c for c in rule_cols if c in result.columns]
        agg_exprs: list[Any] = [F.sum(F.when(F.col(c), 1).otherwise(0)).alias(c) for c in present]
        agg_exprs.append(F.count(F.lit(1)).alias("_total_rows"))
        row = result.agg(*agg_exprs).collect()[0]
        counts: dict[str, int] = {c: int(row[c]) for c in present}
        counts["_total_rows"] = int(row["_total_rows"])
        return result, counts

    def _apply_strategy_a(self, df: Any) -> Any:
        """Strategy A: SQL_PUSHDOWN - Catalyst-native execution (Req 6).

        Batched into one or two ``select`` calls to avoid O(rules) ``withColumn`` plan growth.
        """
        from pyspark.sql import functions as F

        rules = self.rulepack.sql_pushdown
        if not rules:
            return df

        # Phase 1: original columns + all rule boolean columns (single Project).
        cols_r = [F.col(c) for c in df.columns]
        for rule in rules:
            col_name = _safe_rule_col(rule.name)
            if rule.predicate_sql:
                cols_r.append(
                    F.when(F.expr(rule.predicate_sql), F.lit(True))
                    .otherwise(F.lit(False))
                    .alias(col_name),
                )
            else:
                cols_r.append(F.lit(True).alias(col_name))
        df_rules = df.select(*cols_r)

        # Phase 2: add staging action columns (reference r_* from phase 1).
        cols_a = [F.col(c) for c in df_rules.columns]
        for rule in rules:
            col_name = _safe_rule_col(rule.name)
            for action_field, action_sql in rule.action_sql.items():
                action_col = _staging_action_column(rule, action_field)
                cols_a.append(
                    F.when(F.col(col_name), F.expr(action_sql)).alias(action_col),
                )
        return df_rules.select(*cols_a)

    def _apply_strategy_b(self, df: Any) -> Any:
        """Strategy B: ALPHA_SHARED - shared alpha boolean columns (Req 7).

        Batched into three ``select`` projections plus a ``drop`` (constant depth),
        matching Strategy A's goal of avoiding O(rules × actions) ``withColumn`` chains.
        """
        from pyspark.sql import functions as F

        rules = self.rulepack.alpha_shared
        if not rules:
            return df

        # Build alpha nodes with SQL translations (single AlphaNetwork planning pass).
        asts = [r.ast for r in self.rulepack.rules]
        if self._alpha_net_plan is None:
            self._alpha_net_plan = AlphaNetwork.from_rules(asts)
        net_plan = self._alpha_net_plan
        alpha_sql: dict[str, str] = {}
        rule_alpha_map: dict[str, list[str]] = {}

        for rule in rules:
            hashes = list(rule.alpha_hashes)
            rule_alpha_map[rule.name] = hashes
            for h in hashes:
                if h not in alpha_sql:
                    node = net_plan.nodes.get(h)
                    if node:
                        try:
                            alpha_sql[h] = translate_predicate(node.expr)
                        except Exception:  # noqa: BLE001
                            from sparkrules.runtime.engine_metrics import (
                                record_translation_failure,
                            )

                            record_translation_failure()
                            alpha_sql[h] = "true"

        # Phase 1: original columns + all alpha booleans (single Project).
        cols_alpha = [F.col(c) for c in df.columns]
        for h, sql in alpha_sql.items():
            alpha_col = f"_a_{h}"
            cols_alpha.append(F.expr(sql).cast("boolean").alias(alpha_col))
        df_alpha = df.select(*cols_alpha)

        # Phase 2: AND-reduce per rule into r_* (single Project).
        cols_rules = [F.col(c) for c in df_alpha.columns]
        for rule in rules:
            col_name = _safe_rule_col(rule.name)
            alpha_cols = [f"_a_{h}" for h in rule_alpha_map.get(rule.name, [])]
            if alpha_cols:
                expr = F.col(alpha_cols[0])
                for ac in alpha_cols[1:]:
                    expr = expr & F.col(ac)
                cols_rules.append(expr.alias(col_name))
            else:
                cols_rules.append(F.lit(True).alias(col_name))
        df_rules = df_alpha.select(*cols_rules)

        # Phase 3: staging action columns (single Project).
        cols_actions = [F.col(c) for c in df_rules.columns]
        for rule in rules:
            col_name = _safe_rule_col(rule.name)
            for action_field, action_sql in rule.action_sql.items():
                action_col = _staging_action_column(rule, action_field)
                cols_actions.append(
                    F.when(F.col(col_name), F.expr(action_sql)).alias(action_col),
                )
        result = df_rules.select(*cols_actions)

        # Req 16: Drop temporary alpha columns
        alpha_cols_to_drop = [f"_a_{h}" for h in alpha_sql]
        return result.drop(*alpha_cols_to_drop)

    def _apply_strategy_c(self, df: Any) -> Any:
        """Strategy C: PYTHON_FALLBACK - mapPartitions with broadcast (Req 8, 20)."""
        from pyspark.sql import Row
        from pyspark.sql.types import (
            BooleanType,
            StringType,
            StructField,
            StructType,
        )

        rules = self.rulepack.python_fallback
        if not rules:
            return df

        # Broadcast RuleAst list + salience metadata (avoids re-parsing DRL on every partition).
        spark = df.sparkSession
        sc = spark.sparkContext
        bc_asts = sc.broadcast([r.ast for r in rules])
        meta_bc = sc.broadcast({r.name: (r.salience, r.source_order) for r in rules})

        def _eval_partition(partition: Any) -> Any:
            """Evaluate fallback rules per partition (Req 8, AC 2-3)."""
            from sparkrules.compiler.alpha_network import AlphaNetwork as AN
            from sparkrules.compiler.closure import compile_action as ca

            ast_list = bc_asts.value
            meta = meta_bc.value
            net = AN.from_rules(ast_list)

            action_fns: dict[str, list[tuple[str, Any]]] = {}
            for rule in ast_list:
                fns = []
                for action in rule.then:
                    fname, fn = ca(action)
                    fns.append((fname, fn))
                action_fns[rule.name] = fns

            for row in partition:
                if hasattr(row, "asDict"):
                    try:
                        fact = row.asDict(recursive=True)
                    except TypeError:
                        fact = row.asDict()
                else:
                    fact = dict(row)

                fired_map = net.evaluate(fact)
                result_row = dict(fact)

                for rule in ast_list:
                    col = _safe_rule_col(rule.name)
                    fired = fired_map.get(rule.name, False)
                    result_row[col] = fired
                    salience, source_order = meta[rule.name]
                    if fired:
                        for fname, fn in action_fns.get(rule.name, []):
                            acol = _staging_action_flat(salience, source_order, fname)
                            try:
                                result_row[acol] = fn(fact)
                            except Exception:  # noqa: BLE001
                                result_row[acol] = None

                yield Row(**result_row)

        result_rdd = df.rdd.mapPartitions(_eval_partition)

        # Build schema: original + rule columns + action columns
        new_fields = list(df.schema.fields)
        for rule in rules:
            new_fields.append(StructField(_safe_rule_col(rule.name), BooleanType(), True))
            for action_field in _action_fields_from_ast(rule):
                new_fields.append(
                    StructField(
                        _staging_action_column(rule, action_field),
                        StringType(),
                        True,
                    )
                )

        result_schema = StructType(new_fields)
        return spark.createDataFrame(result_rdd, result_schema)

    def _merge_actions(self, df: Any) -> Any:
        """Req 17: Cross-strategy salience resolution."""
        from pyspark.sql import functions as F

        action_fields = action_staging_merge_plan(self.rulepack, df_columns=frozenset(df.columns))

        result = df
        for field_name, salience_cols in action_fields.items():
            merged_col = _safe_action_col(field_name)

            dtypes = _staging_dtypes_for_merge(result, salience_cols)
            sql_type = _common_coalesce_sql_type(dtypes)
            if len(salience_cols) == 1:
                merged_expr = F.col(salience_cols[0][-1]).cast(sql_type)
            else:
                col_refs = [F.col(t[-1]).cast(sql_type) for t in salience_cols]
                merged_expr = F.coalesce(*col_refs)
            result = result.withColumn(merged_col, merged_expr)

            for t in salience_cols:
                result = result.drop(t[-1])

        return result

    def _to_narrow_output(self, result: Any) -> Any:
        """Collapse wide rule/action columns into ``fired_rules`` + ``actions`` struct."""
        from pyspark.sql import functions as F

        plan = action_staging_merge_plan(self.rulepack, df_columns=frozenset(result.columns))
        rule_cols = [_safe_rule_col(r.name) for r in self.rulepack.rules]
        present_rules = [c for c in rule_cols if c in result.columns]
        fired_parts: list[Any] = []
        for r in self.rulepack.rules:
            c = _safe_rule_col(r.name)
            if c in result.columns:
                fired_parts.append(F.when(F.col(c), F.lit(r.name)).otherwise(F.lit(None)))
        if fired_parts:
            fired_expr = F.array_compact(F.array(*fired_parts))
        else:
            fired_expr = F.array().cast("array<string>")

        struct_parts: list[Any] = []
        for field_name in plan:
            mc = _safe_action_col(field_name)
            if mc in result.columns:
                struct_parts.append(F.col(mc).alias(field_name))
        actions_expr = F.struct(*struct_parts) if struct_parts else F.struct()

        drop_names = set(present_rules)
        drop_names.update(
            _safe_action_col(fn) for fn in plan if _safe_action_col(fn) in result.columns
        )
        drop_names.add("fired_any")
        keep = [c for c in result.columns if c not in drop_names]
        select_exprs = [F.col(c) for c in keep]
        select_exprs.extend(
            [
                fired_expr.alias("fired_rules"),
                actions_expr.alias("actions"),
                F.col("fired_any")
                if "fired_any" in result.columns
                else F.lit(False).alias("fired_any"),
            ],
        )
        return result.select(*select_exprs)

    def refresh_rules(self, drl: str) -> None:
        """Hot-swap rules without restarting SparkSession (Req 23)."""
        self.rulepack = RulePack.from_drl(drl)
        self._drl = drl
        self._alpha_net_plan = None

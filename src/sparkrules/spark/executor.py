"""SparkRuleExecutor - V2 optimized Spark execution (Requirements 6-8, 10, 15-17, 20, 24).

Dispatches classified rules to three strategies:
- Strategy A (SQL_PUSHDOWN): F.expr() / F.when() - Catalyst-optimized, zero Python workers
- Strategy B (ALPHA_SHARED): shared alpha boolean columns + AND-reduction
- Strategy C (PYTHON_FALLBACK): mapPartitions with broadcast alpha network

Cross-path equivalence with LocalRuleExecutor is a hard requirement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sparkrules.compiler.alpha_network import AlphaNetwork
from sparkrules.compiler.rulepack import ClassifiedRule, RulePack
from sparkrules.compiler.translator import translate_predicate


class SchemaValidationError(TypeError):
    """Raised when facts DataFrame has MapType where StructType is expected (Req 15)."""

    pass


_SAFE_SPARK_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


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

    @staticmethod
    def from_drl(drl: str) -> SparkRuleExecutor:
        pack = RulePack.from_drl(drl)
        return SparkRuleExecutor(rulepack=pack, _drl=drl)

    def apply(self, df: Any) -> Any:  # pragma: no cover
        """Execute all rules against a Spark DataFrame.

        Returns DataFrame with: original columns + r_<rule> booleans +
        action_<field> typed columns + fired_any boolean.
        """
        from pyspark.sql import functions as F
        from pyspark.sql.types import MapType

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

        # fired_any column (Req 10)
        rule_cols = [_safe_rule_col(r.name) for r in self.rulepack.rules]
        if rule_cols:
            result = result.withColumn(
                "fired_any",
                F.greatest(*[F.col(c) for c in rule_cols if c in result.columns]),
            )
        else:
            result = result.withColumn("fired_any", F.lit(False))

        return result

    def _apply_strategy_a(self, df: Any) -> Any:  # pragma: no cover
        """Strategy A: SQL_PUSHDOWN - Catalyst-native execution (Req 6)."""
        from pyspark.sql import functions as F

        rules = self.rulepack.sql_pushdown
        if not rules:
            return df

        result = df
        for rule in rules:
            col_name = _safe_rule_col(rule.name)
            if rule.predicate_sql:
                result = result.withColumn(
                    col_name,
                    F.when(F.expr(rule.predicate_sql), F.lit(True)).otherwise(F.lit(False)),
                )
            else:
                result = result.withColumn(col_name, F.lit(True))

            # Typed action columns (Req 10)
            for action_field, action_sql in rule.action_sql.items():
                action_col = _staging_action_column(rule, action_field)
                result = result.withColumn(
                    action_col,
                    F.when(F.col(col_name), F.expr(action_sql)),
                )

        return result

    def _apply_strategy_b(self, df: Any) -> Any:  # pragma: no cover
        """Strategy B: ALPHA_SHARED - shared alpha boolean columns (Req 7)."""
        from pyspark.sql import functions as F

        rules = self.rulepack.alpha_shared
        if not rules:
            return df

        # Build alpha nodes with SQL translations
        alpha_sql: dict[str, str] = {}
        rule_alpha_map: dict[str, list[str]] = {}

        for rule in rules:
            hashes = list(rule.alpha_hashes)
            rule_alpha_map[rule.name] = hashes
            for h in hashes:
                if h not in alpha_sql:
                    # Find the alpha node and translate its expression
                    asts = [r.ast for r in self.rulepack.rules]
                    net = AlphaNetwork.from_rules(asts)
                    node = net.nodes.get(h)
                    if node:
                        try:
                            alpha_sql[h] = translate_predicate(node.expr)
                        except Exception:  # noqa: BLE001
                            alpha_sql[h] = "true"

        result = df

        # Add alpha boolean columns (Req 7, AC 1)
        for h, sql in alpha_sql.items():
            alpha_col = f"_a_{h}"
            result = result.withColumn(alpha_col, F.expr(sql).cast("boolean"))

        # AND-reduce per rule (Req 7, AC 2)
        for rule in rules:
            col_name = _safe_rule_col(rule.name)
            alpha_cols = [f"_a_{h}" for h in rule_alpha_map.get(rule.name, [])]
            if alpha_cols:
                expr = F.col(alpha_cols[0])
                for ac in alpha_cols[1:]:
                    expr = expr & F.col(ac)
                result = result.withColumn(col_name, expr)
            else:
                result = result.withColumn(col_name, F.lit(True))

            # Action columns
            for action_field, action_sql in rule.action_sql.items():
                action_col = _staging_action_column(rule, action_field)
                result = result.withColumn(
                    action_col,
                    F.when(F.col(col_name), F.expr(action_sql)),
                )

        # Req 16: Drop temporary alpha columns
        alpha_cols_to_drop = [f"_a_{h}" for h in alpha_sql]
        result = result.drop(*alpha_cols_to_drop)

        return result

    def _apply_strategy_c(self, df: Any) -> Any:  # pragma: no cover
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

        # Req 20: Broadcast DRL string (pickle-safe), not closures
        spark = df.sparkSession
        sc = spark.sparkContext
        drl_broadcast = sc.broadcast(self._drl)
        rule_names = [r.name for r in rules]
        rule_names_broadcast = sc.broadcast(rule_names)
        source_order_broadcast = sc.broadcast({r.name: r.source_order for r in rules})

        def _eval_partition(partition: Any) -> Any:
            """Evaluate fallback rules per partition (Req 8, AC 2-3)."""
            # Reconstruct once per partition, not per row (Req 20, AC 3)
            from sparkrules.compiler.alpha_network import AlphaNetwork as AN
            from sparkrules.compiler.closure import compile_action as ca
            from sparkrules.parser import parse_rules as pr

            drl_val = drl_broadcast.value
            target_names = set(rule_names_broadcast.value)
            source_orders = source_order_broadcast.value
            all_rules = pr(drl_val)
            target_rules = [r for r in all_rules if r.name in target_names]
            net = AN.from_rules(target_rules)

            # Pre-compile actions
            action_fns: dict[str, list[tuple[str, Any]]] = {}
            for rule in target_rules:
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

                for rule in target_rules:
                    col = _safe_rule_col(rule.name)
                    fired = fired_map.get(rule.name, False)
                    result_row[col] = fired
                    if fired:
                        for fname, fn in action_fns.get(rule.name, []):
                            so = source_orders.get(rule.name, 0)
                            acol = _staging_action_flat(rule.salience, so, fname)
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
            for action_field in rule.action_sql:
                new_fields.append(
                    StructField(
                        _staging_action_column(rule, action_field),
                        StringType(),
                        True,
                    )
                )

        result_schema = StructType(new_fields)
        return spark.createDataFrame(result_rdd, result_schema)

    def _merge_actions(self, df: Any) -> Any:  # pragma: no cover
        """Req 17: Cross-strategy salience resolution."""
        from pyspark.sql import functions as F

        # Collect all action columns grouped by field name (Req 17 tie-breakers)
        action_fields: dict[str, list[tuple[int, str, int, str]]] = {}
        for rule in self.rulepack.rules:
            for action_field in rule.action_sql:
                col_name = _staging_action_column(rule, action_field)
                if col_name in df.columns:
                    if action_field not in action_fields:
                        action_fields[action_field] = []
                    action_fields[action_field].append(
                        (rule.salience, rule.name, rule.source_order, col_name),
                    )

        result = df
        for field_name, salience_cols in action_fields.items():
            salience_cols.sort(key=lambda x: (-x[0], x[1], x[2]))
            merged_col = _safe_action_col(field_name)

            # Build COALESCE chain (first non-null wins)
            col_refs = [F.col(t[-1]) for t in salience_cols]
            result = result.withColumn(merged_col, F.coalesce(*col_refs))

            # Drop intermediate salience-tagged columns
            for t in salience_cols:
                result = result.drop(t[-1])

        return result

    def refresh_rules(self, drl: str) -> None:
        """Hot-swap rules without restarting SparkSession (Req 23)."""
        self.rulepack = RulePack.from_drl(drl)
        self._drl = drl

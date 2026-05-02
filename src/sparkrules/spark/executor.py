"""SparkRuleExecutor - V2 optimized Spark execution (Requirements 6-8, 10, 15-17, 20, 24).

Dispatches classified rules to three strategies:
- Strategy A (SQL_PUSHDOWN): F.expr() / F.when() - Catalyst-optimized, zero Python workers
- Strategy B (ALPHA_SHARED): shared alpha boolean columns + AND-reduction
- Strategy C (PYTHON_FALLBACK): mapPartitions with broadcast alpha network

Cross-path equivalence with LocalRuleExecutor is a hard requirement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sparkrules.compiler.alpha_network import AlphaNetwork
from sparkrules.compiler.closure import compile_action, compile_predicate
from sparkrules.compiler.rulepack import ClassifiedRule, RulePack, Strategy
from sparkrules.compiler.translator import translate_predicate


class SchemaValidationError(TypeError):
    """Raised when facts DataFrame has MapType where StructType is expected (Req 15)."""

    pass


def _safe_rule_col(name: str) -> str:
    """Sanitize rule name for use as a Spark column name."""
    return "r_" + name.replace("-", "_").replace(" ", "_").replace('"', "")


def _safe_action_col(field_name: str) -> str:
    return "action_" + field_name.replace("-", "_").replace(" ", "_")


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
                action_col = _safe_action_col(action_field) + "__s" + str(rule.salience)
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
                action_col = _safe_action_col(action_field) + "__s" + str(rule.salience)
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
        from pyspark.sql import Row, functions as F
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

        # Collect existing columns
        existing_cols = df.columns

        def _eval_partition(partition: Any) -> Any:
            """Evaluate fallback rules per partition (Req 8, AC 2-3)."""
            # Reconstruct once per partition, not per row (Req 20, AC 3)
            from sparkrules.compiler.alpha_network import AlphaNetwork as AN
            from sparkrules.compiler.closure import compile_action as ca
            from sparkrules.parser import parse_rules as pr

            drl_val = drl_broadcast.value
            target_names = set(rule_names_broadcast.value)
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
                            acol = _safe_action_col(fname) + "__s" + str(rule.salience)
                            try:
                                result_row[acol] = fn(fact)
                            except Exception:  # noqa: BLE001
                                result_row[acol] = None

                yield Row(**result_row)

        result_rdd = df.rdd.mapPartitions(_eval_partition)

        # Build schema: original + rule columns + action columns
        from pyspark.sql.types import StructType

        new_fields = list(df.schema.fields)
        for rule in rules:
            new_fields.append(StructField(_safe_rule_col(rule.name), BooleanType(), True))
            for action_field in rule.action_sql:
                new_fields.append(
                    StructField(
                        _safe_action_col(action_field) + "__s" + str(rule.salience),
                        StringType(),
                        True,
                    )
                )

        result_schema = StructType(new_fields)
        return spark.createDataFrame(result_rdd, result_schema)

    def _merge_actions(self, df: Any) -> Any:  # pragma: no cover
        """Req 17: Cross-strategy salience resolution."""
        from pyspark.sql import functions as F

        # Collect all action columns grouped by field name
        action_fields: dict[str, list[tuple[int, str]]] = {}
        for rule in self.rulepack.rules:
            for action_field in rule.action_sql:
                col_name = _safe_action_col(action_field) + "__s" + str(rule.salience)
                if col_name in df.columns:
                    if action_field not in action_fields:
                        action_fields[action_field] = []
                    action_fields[action_field].append((rule.salience, col_name))

        result = df
        for field_name, salience_cols in action_fields.items():
            # Sort by salience descending - highest wins
            salience_cols.sort(key=lambda x: -x[0])
            merged_col = _safe_action_col(field_name)

            # Build COALESCE chain (first non-null wins, ordered by salience)
            col_refs = [F.col(c) for _, c in salience_cols]
            result = result.withColumn(merged_col, F.coalesce(*col_refs))

            # Drop intermediate salience-tagged columns
            for _, c in salience_cols:
                result = result.drop(c)

        return result

    def refresh_rules(self, drl: str) -> None:
        """Hot-swap rules without restarting SparkSession (Req 23)."""
        self.rulepack = RulePack.from_drl(drl)
        self._drl = drl

"""AST-to-SQL Translator (Requirement 1).

Converts DRL predicate AST nodes into Spark SQL expression strings
consumable by pyspark.sql.functions.expr(). Also translates action
expressions for Strategy A (SQL_PUSHDOWN).
"""

from __future__ import annotations

from sparkrules.parser.ast import (
    BinaryOp,
    BinaryOperator,
    CallExpr,
    Expr,
    Identifier,
    InExpr,
    ListExpr,
    Literal,
    Not,
    Action,
)


class TranslationError(Exception):
    """Raised when an AST node cannot be translated to Spark SQL."""

    def __init__(self, message: str, node_type: str = "") -> None:
        self.node_type = node_type
        super().__init__(message)


def _sql_string_literal(value: str) -> str:
    """SQL string literal escape (ANSI doubling of single-quote)."""

    return "'" + value.replace("'", "''") + "'"


def _spark_rlike_pattern_literal(pattern: str) -> str:
    """Embed a regex pattern into a Spark SQL literal (Java regex consumes ``\\`` as ``\\\\``).

    Drools/Python ``matches`` semantics are anchored to Spark ``RLIKE``; backslashes must
    survive SQL parsing before the regex engine interprets escapes like ``\\d``.
    """

    return "'" + pattern.replace("\\", "\\\\").replace("'", "''") + "'"


def translate_predicate(expr: Expr, *, strip_binding: bool = True) -> str:
    """Translate a predicate AST to a Spark SQL expression string.

    Args:
        expr: The predicate AST node.
        strip_binding: If True, strip the $ prefix from identifiers
                       and convert $t.field to t.field (Spark struct access).

    Returns:
        A Spark SQL expression string.

    Raises:
        TranslationError: If the AST contains untranslatable nodes.
    """
    if isinstance(expr, Literal):
        if isinstance(expr.value, str):
            return _sql_string_literal(expr.value)
        if isinstance(expr.value, bool):
            return "true" if expr.value else "false"
        if expr.value is None:
            return "NULL"
        return str(expr.value)

    if isinstance(expr, Identifier):
        name = expr.name
        if strip_binding and name.startswith("$"):
            name = name[1:]
        return name

    if isinstance(expr, BinaryOp):
        if expr.op == BinaryOperator.MATCHES:
            left = translate_predicate(expr.left, strip_binding=strip_binding)
            if isinstance(expr.right, Literal) and isinstance(expr.right.value, str):
                rp = _spark_rlike_pattern_literal(str(expr.right.value))
            else:
                rp = translate_predicate(expr.right, strip_binding=strip_binding)
            return f"({left} RLIKE {rp})"

        left = translate_predicate(expr.left, strip_binding=strip_binding)
        right = translate_predicate(expr.right, strip_binding=strip_binding)

        op_map = {
            BinaryOperator.EQ: "=",
            BinaryOperator.NE: "!=",
            BinaryOperator.LT: "<",
            BinaryOperator.LE: "<=",
            BinaryOperator.GT: ">",
            BinaryOperator.GE: ">=",
        }

        if expr.op in op_map:
            return f"({left} {op_map[expr.op]} {right})"
        if expr.op == BinaryOperator.AND:
            return f"({left} AND {right})"
        if expr.op == BinaryOperator.OR:
            return f"({left} OR {right})"
        if expr.op == BinaryOperator.CONTAINS:
            # Python ``right in left``: arrays -> ``array_contains``; strings/other scalars ->
            # substring containment via ``instr`` (parity with Drools-ish ``contains`` on text).
            return (
                f"(CASE WHEN typeof({left}) LIKE 'array%' THEN array_contains({left}, {right}) "
                f"ELSE (instr(cast({left} AS STRING), cast({right} AS STRING)) > 0) END)"
            )

        raise TranslationError(  # pragma: no cover
            f"Unsupported binary operator: {expr.op}", node_type="BinaryOp"
        )

    if isinstance(expr, Not):
        inner = translate_predicate(expr.expr, strip_binding=strip_binding)
        return f"(NOT {inner})"

    if isinstance(expr, InExpr):
        left = translate_predicate(expr.left, strip_binding=strip_binding)
        if isinstance(expr.right, ListExpr):
            items = ", ".join(
                translate_predicate(it, strip_binding=strip_binding) for it in expr.right.items
            )
            if expr.negated:
                return f"({left} NOT IN ({items}))"
            return f"({left} IN ({items}))"
        if isinstance(expr.right, Identifier):
            raise TranslationError(
                "``IN`` with a non-literal list cannot be reliably translated without "
                "ARRAY-typed Spark columns — use ALPHA_SHARED / PYTHON_FALLBACK or expose "
                "``array_contains`` explicitly",
                node_type="InExpr",
            )
        right = translate_predicate(expr.right, strip_binding=strip_binding)
        if expr.negated:
            return f"(NOT array_contains({right}, {left}))"
        return f"array_contains({right}, {left})"

    if isinstance(expr, ListExpr):
        items = ", ".join(translate_predicate(it, strip_binding=strip_binding) for it in expr.items)
        return f"array({items})"

    if isinstance(expr, CallExpr):
        args = ", ".join(translate_predicate(a, strip_binding=strip_binding) for a in expr.args)
        return f"{expr.name}({args})"

    raise TranslationError(
        f"Unsupported AST node type: {type(expr).__name__}",
        node_type=type(expr).__name__,
    )


def translate_action(action: Action, *, strip_binding: bool = True) -> tuple[str, str]:
    """Translate an action AST to (field_name, sql_value_expr).

    Returns:
        Tuple of (output field name, Spark SQL value expression).
    """
    field = action.field_path.replace("result.", "")
    value_sql = translate_predicate(action.expr, strip_binding=strip_binding)
    return field, value_sql


def can_translate(expr: Expr) -> bool:
    """Check if a predicate AST can be fully translated to Spark SQL."""
    try:
        translate_predicate(expr)
        return True
    except TranslationError:
        return False

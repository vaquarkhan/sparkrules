"""Export SparkRules DRL rules to OPA Rego policy format.

Generates a Rego policy file that security teams can verify with their
existing OPA toolchain. Supports basic comparison operators and boolean logic.
"""

from __future__ import annotations

from typing import Any

from sparkrules.parser import parse_rules
from sparkrules.parser.ast import (
    Action,
    BinaryOp,
    BinaryOperator,
    CallExpr,
    Expr,
    FactPattern,
    Identifier,
    InExpr,
    ListExpr,
    Literal,
    Not,
    RuleAst,
)


def _expr_to_rego(expr: Expr, binding: str = "input") -> str:
    """Convert a SparkRules AST expression to Rego syntax."""
    if isinstance(expr, Literal):
        if isinstance(expr.value, str):
            return f'"{expr.value}"'
        if isinstance(expr.value, bool):
            return "true" if expr.value else "false"
        if expr.value is None:
            return "null"
        return str(expr.value)

    if isinstance(expr, Identifier):
        name = expr.name
        if name.startswith("$"):
            name = name[1:]
        parts = name.split(".")
        if len(parts) > 1:
            return f"{binding}.{'.'.join(parts[1:])}"
        return f"{binding}.{name}"

    if isinstance(expr, BinaryOp):
        left = _expr_to_rego(expr.left, binding)
        right = _expr_to_rego(expr.right, binding)
        op_map = {
            BinaryOperator.EQ: "==",
            BinaryOperator.NE: "!=",
            BinaryOperator.LT: "<",
            BinaryOperator.LE: "<=",
            BinaryOperator.GT: ">",
            BinaryOperator.GE: ">=",
            BinaryOperator.AND: "\n    ",
            BinaryOperator.OR: "} {\n    # OR branch\n    ",
        }
        op = op_map.get(expr.op, "==")
        if expr.op == BinaryOperator.AND:
            return f"{left}{op}{right}"
        if expr.op == BinaryOperator.OR:
            return f"{left}{op}{right}"
        if expr.op == BinaryOperator.CONTAINS:
            return f"{right} == {left}[_]"
        if expr.op == BinaryOperator.MATCHES:
            return f'regex.match({right}, {left})'
        return f"{left} {op} {right}"

    if isinstance(expr, Not):
        inner = _expr_to_rego(expr.expr, binding)
        return f"not {inner}"

    if isinstance(expr, InExpr):
        left = _expr_to_rego(expr.left, binding)
        if isinstance(expr.right, ListExpr):
            items = ", ".join(_expr_to_rego(it, binding) for it in expr.right.items)
            set_expr = f"{{{items}}}"
            if expr.negated:
                return f"not {set_expr}[{left}]"
            return f"{set_expr}[{left}]"
        right = _expr_to_rego(expr.right, binding)
        if expr.negated:
            return f"not {right}[{left}]"
        return f"{right}[{left}]"

    if isinstance(expr, ListExpr):
        items = ", ".join(_expr_to_rego(it, binding) for it in expr.items)
        return f"[{items}]"

    if isinstance(expr, CallExpr):
        args = ", ".join(_expr_to_rego(a, binding) for a in expr.args)
        return f"{expr.name}({args})"

    return f"# unsupported: {type(expr).__name__}"


def _rule_to_rego(rule: RuleAst, binding: str = "input") -> str:
    """Convert a single RuleAst to a Rego rule block."""
    safe_name = rule.name.replace("-", "_").replace(" ", "_").replace('"', "")
    lines: list[str] = []
    lines.append(f"# Rule: {rule.name} (salience: {rule.salience})")
    if rule.reason_codes:
        codes = ", ".join(f'"{c}"' for c in rule.reason_codes)
        lines.append(f"# Reason codes: [{codes}]")

    lines.append(f"{safe_name} = result {{")

    # Conditions
    for pattern in rule.when:
        if pattern.constraint is not None:
            cond = _expr_to_rego(pattern.constraint, binding)
            lines.append(f"    {cond}")

    # Actions → result object
    result_fields: list[str] = []
    for action in rule.then:
        field = action.field_path.replace("result.", "")
        val = _expr_to_rego(action.expr, binding)
        result_fields.append(f'        "{field}": {val}')

    if result_fields:
        lines.append("    result := {")
        lines.append(",\n".join(result_fields))
        lines.append("    }")
    else:
        lines.append('    result := {"fired": true}')

    lines.append("}")
    return "\n".join(lines)


def export_to_rego(
    drl: str,
    *,
    package_name: str = "sparkrules.policy",
) -> str:
    """Export DRL rules to an OPA Rego policy string.

    Args:
        drl: One or more DRL rules as a string.
        package_name: Rego package name (default: sparkrules.policy).

    Returns:
        A Rego policy string that can be loaded by OPA.
    """
    rules = parse_rules(drl)
    lines: list[str] = []
    lines.append(f"package {package_name}")
    lines.append("")
    lines.append("# Auto-generated from SparkRules DRL")
    lines.append(f"# Rules: {len(rules)}")
    lines.append("")

    for rule in rules:
        lines.append(_rule_to_rego(rule))
        lines.append("")

    return "\n".join(lines)

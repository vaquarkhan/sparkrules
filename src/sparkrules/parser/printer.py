from __future__ import annotations

from sparkrules.model.rule import DEFAULT_AGENDA_GROUP
from sparkrules.parser import ast as A
from sparkrules.parser.ast import Action, BinaryOperator, Expr, FactPattern, RuleAst

_BIN_STR = {
    BinaryOperator.EQ: "==",
    BinaryOperator.NE: "!=",
    BinaryOperator.LT: "<",
    BinaryOperator.LE: "<=",
    BinaryOperator.GT: ">",
    BinaryOperator.GE: ">=",
    BinaryOperator.AND: "and",
    BinaryOperator.OR: "or",
    BinaryOperator.IN: "in",
    BinaryOperator.NOT_IN: "not in",
    BinaryOperator.CONTAINS: "contains",
    BinaryOperator.MATCHES: "matches",
}


def _quote(s: str) -> str:
    if any(c in s for c in " \t\n"):
        return repr(s)
    if '"' not in s:
        return f'"{s}"'
    return repr(s)


def _print_expr(e: A.Expr) -> str:
    if isinstance(e, A.Literal):
        v = e.value
        if v is True:
            return "true"
        if v is False:
            return "false"
        if v is None:
            return "null"
        if isinstance(v, str):
            return _quote(v)
        return str(v)
    if isinstance(e, A.Identifier):
        return e.name
    if isinstance(e, A.Not):
        return f"not ({_print_expr(e.expr)})"
    if isinstance(e, A.ListExpr):
        return "[" + ", ".join(_print_expr(x) for x in e.items) + "]"
    if isinstance(e, A.InExpr):
        op = "not in" if e.negated else "in"
        return f"({_print_expr(e.left)} {op} {_print_expr(e.right)})"
    if isinstance(e, A.CallExpr):
        return e.name + "(" + ", ".join(_print_expr(a) for a in e.args) + ")"
    if isinstance(e, A.BinaryOp):
        return f"({_print_expr(e.left)} {_BIN_STR[e.op]} {_print_expr(e.right)})"
    return str(e)


def _print_pattern(p: FactPattern) -> str:
    c = p.constraint
    inner = "" if c is None else _print_expr(c)
    if inner:
        return f"${p.bind_name} : {p.fact_type} ( {inner} )"
    return f"${p.bind_name} : {p.fact_type} ( )"


def _print_action(a: Action) -> str:
    return f"{a.field_path} = {_print_expr(a.expr)};"


def print_ast_expr(expr: Expr) -> str:
    """Print an expression AST node as a string (for hashing/comparison)."""
    return _print_expr(expr)


def print_ast(rule: RuleAst) -> str:
    lines: list[str] = []
    nm = _quote(rule.name) if " " in rule.name or not rule.name.isidentifier() else rule.name
    lines.append(f"rule {nm}")
    if rule.salience:
        lines.append(f"    salience {rule.salience}")
    if rule.agenda_group != DEFAULT_AGENDA_GROUP:
        lines.append(f"    agenda_group {_quote(rule.agenda_group)}")
    if rule.activation_group is not None:
        lines.append(f"    activation_group {_quote(rule.activation_group)}")
    if rule.pass_name:
        lines.append(f"    pass {rule.pass_name}")
    if rule.group_by:
        items = ", ".join(_quote(x) for x in rule.group_by)
        lines.append(f"    group_by [ {items} ]")
    if rule.reason_codes:
        items = ", ".join(_quote(x) for x in rule.reason_codes)
        lines.append(f"    reason_codes [ {items} ]")
    if rule.stop_on_fire:
        lines.append("    stop_on_fire true")
    lines.append("when")
    whens = " and ".join(_print_pattern(p) for p in rule.when)
    lines.append("    " + whens)
    lines.append("then")
    for a in rule.then:
        lines.append("    " + _print_action(a))
    lines.append("end")
    return "\n".join(lines) + "\n"


class DrlPrinter:
    def __init__(self) -> None:
        pass

    def print(self, rule: RuleAst) -> str:
        return print_ast(rule)

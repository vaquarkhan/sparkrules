from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, MutableMapping

import sre.parser.ast as A
from sre.parser.ast import BinaryOperator, Expr, RuleAst


@dataclass(frozen=True, slots=True)
class RuleMatch:
    rule_name: str
    fired: bool
    bound: dict[str, Any]
    action_output: dict[str, Any]


def _get_id(name: str, env: dict[str, Any]) -> Any:
    if name == "result":
        return env.get("result")
    if name.startswith("result."):
        o: Any = env.get("result", {})
        for p in name.split(".")[1:]:
            if not isinstance(o, dict):
                return None
            o = o.get(p)
        return o
    raw = name[1:] if name.startswith("$") else name
    parts = raw.split(".")
    o = env.get(parts[0])
    for p in parts[1:]:
        if o is None:
            return None
        o = o.get(p) if isinstance(o, dict) else None
    return o


def _set_result_path(path: str, value: Any, env: dict[str, Any]) -> None:
    assert path.startswith("result.")
    parts = path.split(".")[1:]
    d: MutableMapping[str, Any] = env.setdefault(  # type: ignore[assignment]
        "result", {}
    )
    if not isinstance(d, dict):
        d = {}
        env["result"] = d
    cur: MutableMapping[str, Any] = d
    for p in parts[:-1]:
        n = cur.get(p)
        if not isinstance(n, dict):
            n = {}
            cur[p] = n
        cur = n
    if parts:
        cur[parts[-1]] = value


def _eval(e: Expr, env: dict[str, Any]) -> Any:
    if isinstance(e, A.Literal):
        return e.value
    if isinstance(e, A.Identifier):
        return _get_id(e.name, env)
    if isinstance(e, A.Not):
        return not _eval(e.expr, env)  # type: ignore[no-any-return]
    if isinstance(e, A.ListExpr):
        return [_eval(x, env) for x in e.items]
    if isinstance(e, A.InExpr):
        a, b = _eval(e.left, env), _eval(e.right, env)
        s = set(b) if isinstance(b, (list, tuple, set)) else {b}  # noqa: E501
        return (a not in s) if e.negated else (a in s)  # type: ignore[no-any-return]  # noqa: E501
    if isinstance(e, A.FieldAccess):
        o = env.get(e.base)
        if isinstance(o, dict):
            return o.get(e.field)
        return None
    if isinstance(e, A.CallExpr):
        if e.name == "abs" and e.args:
            v = _eval(e.args[0], env)
            return abs(v) if isinstance(v, (int, float)) else v
        raise ValueError(f"unknown function {e.name}")
    if isinstance(e, A.BinaryOp):
        a, b = _eval(e.left, env), _eval(e.right, env)
        op = e.op
        if op == BinaryOperator.AND:
            return bool(a) and bool(b)
        if op == BinaryOperator.OR:
            return bool(a) or bool(b)
        if op == BinaryOperator.CONTAINS:
            return str(b) in str(a) if a is not None and b is not None else False
        if op == BinaryOperator.MATCHES:
            return re.search(str(b), str(a or "")) is not None
        if op == BinaryOperator.EQ:
            return a == b
        if op == BinaryOperator.NE:
            return a != b
        if op == BinaryOperator.LT:
            return a < b  # type: ignore[no-any-return]
        if op == BinaryOperator.LE:
            return a <= b  # type: ignore[no-any-return]
        if op == BinaryOperator.GT:
            return a > b  # type: ignore[no-any-return]
        if op == BinaryOperator.GE:
            return a >= b  # type: ignore[no-any-return]
    raise TypeError(type(e).__name__)


def evaluate_expr(expr: Expr, bindings: dict[str, Any]) -> Any:
    return _eval(expr, bindings)


def evaluate_rule(
    rule: RuleAst, facts: MutableMapping[str, Any]
) -> RuleMatch:
    env: dict[str, Any] = {k: v for k, v in facts.items()}
    env["result"] = {}
    for pat in rule.when:
        c = pat.constraint
        if c is not None and not _eval(c, env):
            return RuleMatch(
                rule.name, False, {k: v for k, v in env.items() if k != "result"}, {}
            )
    for act in rule.then:
        v = _eval(act.expr, env)
        if act.field_path.startswith("result."):
            _set_result_path(act.field_path, v, env)
    res = env.get("result", {})
    if not isinstance(res, dict):
        res = {}
    return RuleMatch(
        rule.name, True, {k: v for k, v in env.items() if k != "result"}, dict(res)
    )

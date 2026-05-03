"""Closure Compiler (Requirement 2).

Compiles DRL predicate AST nodes into Python closures at parse time,
eliminating per-node isinstance dispatch overhead during evaluation.
"""

from __future__ import annotations

import re
from collections.abc import Mapping as ABCMapping
from typing import Any, Callable, Mapping

from sparkrules.parser.ast import (
    Action,
    BinaryOp,
    BinaryOperator,
    CallExpr,
    Expr,
    Identifier,
    InExpr,
    ListExpr,
    Literal,
    Not,
)

FactDict = Mapping[str, Any]
PredicateFn = Callable[[FactDict], bool]
ActionFn = Callable[[FactDict], Any]


def _resolve_identifier(name: str, fact: FactDict) -> Any:
    """Resolve a dotted identifier path against a fact dict."""
    if name.startswith("$"):
        name = name[1:]
    parts = name.split(".")
    cur: Any = fact
    for part in parts:
        if isinstance(cur, Mapping):
            cur = cur.get(part)
        else:
            return None
    return cur


def compile_predicate(expr: Expr) -> PredicateFn:
    """Compile a predicate AST into a Python closure.

    The returned callable accepts a fact dict and returns bool.
    Runtime errors degrade to False (Req 2, AC 4).
    """
    if isinstance(expr, Literal):
        val = expr.value
        return lambda _f, _v=val: bool(_v)

    if isinstance(expr, Identifier):
        name = expr.name
        return lambda f, _n=name: bool(_resolve_identifier(_n, f))

    if isinstance(expr, Not):
        inner = compile_predicate(expr.expr)
        return lambda f, _i=inner: not _safe(lambda: _i(f))

    if isinstance(expr, BinaryOp):
        left_fn = _compile_value(expr.left)
        right_fn = _compile_value(expr.right)

        if expr.op == BinaryOperator.AND:
            lp = compile_predicate(expr.left)
            rp = compile_predicate(expr.right)
            return lambda f, _l=lp, _r=rp: _safe(lambda: _l(f)) and _safe(lambda: _r(f))

        if expr.op == BinaryOperator.OR:
            lp = compile_predicate(expr.left)
            rp = compile_predicate(expr.right)
            return lambda f, _l=lp, _r=rp: _safe(lambda: _l(f)) or _safe(lambda: _r(f))

        op = expr.op
        return lambda f, _l=left_fn, _r=right_fn, _op=op: _safe(lambda: _compare(_l(f), _r(f), _op))

    if isinstance(expr, InExpr):
        left_fn = _compile_value(expr.left)
        right_fn = _compile_value(expr.right)
        negated = expr.negated
        return lambda f, _l=left_fn, _r=right_fn, _neg=negated: _safe(
            lambda: (
                (_l(f) not in _as_collection(_r(f))) if _neg else (_l(f) in _as_collection(_r(f)))
            )
        )

    # Fallback: try to evaluate as a truthy value
    val_fn = _compile_value(expr)
    return lambda f, _v=val_fn: _safe(lambda: bool(_v(f)))


def _compile_value(expr: Expr) -> Callable[[FactDict], Any]:
    """Compile an expression AST into a value-returning closure."""
    if isinstance(expr, Literal):
        val = expr.value
        return lambda _f, _v=val: _v

    if isinstance(expr, Identifier):
        name = expr.name
        return lambda f, _n=name: _resolve_identifier(_n, f)

    if isinstance(expr, ListExpr):
        item_fns = [_compile_value(it) for it in expr.items]
        return lambda f, _fns=item_fns: [fn(f) for fn in _fns]

    if isinstance(expr, BinaryOp):
        left_fn = _compile_value(expr.left)
        right_fn = _compile_value(expr.right)
        op = expr.op
        if op in (BinaryOperator.AND, BinaryOperator.OR):
            lp = compile_predicate(expr.left)
            rp = compile_predicate(expr.right)
            if op == BinaryOperator.AND:
                return lambda f, _l=lp, _r=rp: _l(f) and _r(f)
            return lambda f, _l=lp, _r=rp: _l(f) or _r(f)
        return lambda f, _l=left_fn, _r=right_fn, _op=op: _compare(_l(f), _r(f), _op)

    if isinstance(expr, Not):
        inner = compile_predicate(expr.expr)
        return lambda f, _i=inner: not _i(f)

    if isinstance(expr, CallExpr):
        arg_fns = [_compile_value(a) for a in expr.args]
        name = expr.name
        return lambda f, _n=name, _a=arg_fns: _call_builtin(_n, [fn(f) for fn in _a])

    if isinstance(expr, InExpr):
        left_fn = _compile_value(expr.left)
        right_fn = _compile_value(expr.right)
        negated = expr.negated
        return lambda f, _l=left_fn, _r=right_fn, _neg=negated: (
            _l(f) not in _as_collection(_r(f)) if _neg else _l(f) in _as_collection(_r(f))
        )

    return lambda _f: None


def compile_action(action: Action) -> tuple[str, ActionFn]:
    """Compile an action AST into (field_name, value_closure).

    Returns:
        Tuple of (output field name, callable that computes the value).
    """
    field = action.field_path.replace("result.", "")
    val_fn = _compile_value(action.expr)
    return field, val_fn


def _compare(left: Any, right: Any, op: BinaryOperator) -> bool:
    """Compare two values using the given operator."""
    if op == BinaryOperator.EQ:
        return left == right
    if op == BinaryOperator.NE:
        return left != right
    if op == BinaryOperator.LT:
        return left < right
    if op == BinaryOperator.LE:
        return left <= right
    if op == BinaryOperator.GT:
        return left > right
    if op == BinaryOperator.GE:
        return left >= right
    if op == BinaryOperator.CONTAINS:
        if isinstance(left, (list, tuple, set, frozenset)):
            return right in left
        if isinstance(left, ABCMapping) and not isinstance(left, (str, bytes)):
            return right in left
        left_s = str(left) if left is not None else ""
        right_s = str(right) if right is not None else ""
        return right_s in left_s if left_s or right_s else False
    if op == BinaryOperator.MATCHES:
        return bool(re.search(str(right), str(left)))
    return False


def _as_collection(val: Any) -> Any:
    """Ensure a value is iterable for 'in' checks."""
    if isinstance(val, (list, tuple, set, frozenset)):
        return val
    return [val]


def _call_builtin(name: str, args: list[Any]) -> Any:
    """Call a built-in function by name."""
    builtins = {"len": len, "str": str, "int": int, "float": float, "abs": abs}
    fn = builtins.get(name)
    if fn is not None:
        return fn(*args)
    return None


def _safe(fn: Callable[[], bool]) -> bool:
    """Evaluate a predicate, returning False on any runtime error (Req 2, AC 4)."""
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return False

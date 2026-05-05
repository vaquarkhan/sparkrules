"""Serialize AST for the Rust Tier-1 scorer (parsed in Python only)."""

from __future__ import annotations

import json
from typing import Any

from sparkrules.compiler.rulepack import RulePack
from sparkrules.parser import ast as A

NATIVE_SCHEMA_VERSION = "1"


def rulepack_to_native_json(pack: RulePack) -> str:
    return json.dumps(
        {
            "drl_hash": pack.drl_hash,
            "native_schema": NATIVE_SCHEMA_VERSION,
            "rules": [serialize_rule(r.ast, source_order=r.source_order) for r in pack.rules],
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _expr(e: A.Expr) -> dict[str, Any]:
    if isinstance(e, A.Literal):
        return {"kind": "Literal", "value": e.value}
    if isinstance(e, A.Identifier):
        return {"kind": "Identifier", "name": e.name}
    if isinstance(e, A.ListExpr):
        return {"kind": "ListExpr", "items": [_expr(x) for x in e.items]}
    if isinstance(e, A.InExpr):
        return {
            "kind": "InExpr",
            "left": _expr(e.left),
            "right": _expr(e.right),
            "negated": e.negated,
        }
    if isinstance(e, A.CallExpr):
        return {"kind": "CallExpr", "name": e.name, "args": [_expr(a) for a in e.args]}
    if isinstance(e, A.FieldAccess):
        return {"kind": "FieldAccess", "base": e.base, "field": e.field}
    if isinstance(e, A.BinaryOp):
        return {
            "kind": "BinaryOp",
            "op": e.op.value,
            "left": _expr(e.left),
            "right": _expr(e.right),
        }
    if isinstance(e, A.Not):
        return {"kind": "Not", "expr": _expr(e.expr)}
    raise TypeError(f"unsupported expr type {type(e).__name__}")


def _pattern(p: A.FactPattern) -> dict[str, Any]:
    return {
        "bind_name": p.bind_name,
        "fact_type": p.fact_type,
        "constraint": None if p.constraint is None else _expr(p.constraint),
    }


def _action(a: A.Action) -> dict[str, Any]:
    return {"field_path": a.field_path, "expr": _expr(a.expr)}


def serialize_rule(ast: A.RuleAst, *, source_order: int) -> dict[str, Any]:
    return {
        "name": ast.name,
        "salience": ast.salience,
        "source_order": source_order,
        "reason_codes": list(ast.reason_codes),
        "when": [_pattern(p) for p in ast.when],
        "then": [_action(a) for a in ast.then],
    }

"""RulePack.native_json contract for Tier-1 Rust."""

from __future__ import annotations

import builtins
import json
import sys
from typing import Any, cast

import pytest

from sparkrules.compiler.rulepack import RulePack
from sparkrules.native import ast_json
from sparkrules.parser import ast as A
from sparkrules.native.ast_json import serialize_rule


def test_to_native_json_includes_rules_and_schema() -> None:
    drl = "rule r when $t : T ( $t.x > 1 ) then result.ok = true; end"
    pack = RulePack.from_drl(drl)
    s = pack.to_native_json()
    blob = json.loads(s)
    assert blob["native_schema"] == "1"
    assert "drl_hash" in blob
    assert len(blob["rules"]) == 1
    assert blob["rules"][0]["name"] == "r"
    assert blob["rules"][0]["then"][0]["field_path"].startswith("result.")


def test_serialize_rule_covers_advanced_expr_shapes() -> None:
    """Exercise ``ast_json._expr`` branches used by richer DRL constructs."""
    drl = """rule cz when $t : T (
        not ( $t.x in [ 1 ] ) or $t.s contains "a"
      ) then
        result.y = len( $t.msg );
      end"""
    ast = RulePack.from_drl(drl).rules[0].ast
    blob = serialize_rule(ast, source_order=0)
    assert blob["when"][0]["constraint"] is not None
    assert blob["then"]


def test_ast_json_field_call_and_typeerror() -> None:
    fc = ast_json._expr(A.CallExpr("abs", (A.Literal(-1),)))  # type: ignore[no-untyped-call]
    assert fc["kind"] == "CallExpr"
    fb = ast_json._expr(  # type: ignore[no-untyped-call]
        A.BinaryOp(A.BinaryOperator.EQ, A.FieldAccess("t", "k"), A.Literal(1)),
    )
    assert fb["left"]["kind"] == "FieldAccess"

    class _Bogus:
        pass

    with pytest.raises(TypeError):
        ast_json._expr(cast(Any, _Bogus()))  # type: ignore[no-untyped-call]


def test_bridge_import_error_returns_none(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "sparkrules_native", raising=False)

    real_import = builtins.__import__

    def _imp(
        name: str,
        globals: Any = None,
        locals: Any = None,
        fromlist: Any = (),
        level: int = 0,
    ):
        if name == "sparkrules_native":
            raise ImportError("simulated missing extension")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _imp)
    from sparkrules.native.bridge import load_native

    assert load_native() is None


def test_executor_raises_when_load_native_returns_none(monkeypatch) -> None:
    import sparkrules.native.executor as nem

    monkeypatch.setattr(nem, "load_native", lambda: None)
    from sparkrules.native.bridge import NativeUnavailableError

    with pytest.raises(NativeUnavailableError):
        nem.NativeRuleExecutor.from_drl("rule zz when $t : T ( true ) then end")
    with pytest.raises(NativeUnavailableError):
        nem.NativeRuleExecutor.from_rulepack(
            RulePack.from_drl("rule zz when $t : T ( true ) then end")
        )

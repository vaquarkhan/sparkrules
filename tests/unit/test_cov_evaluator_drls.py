from __future__ import annotations

import pytest

from sre.compiler import evaluate_expr, evaluate_rule
from sre.parser import parse
import sre.parser.ast as A
from sre.parser.ast import Literal, Identifier, FieldAccess, CallExpr, Not, ListExpr, InExpr


def test_drl_in_not_in() -> None:
    r = parse(
        """
    rule t
    when
    $x : T ( $x in [ 1, 2, 3 ] )
    then
    end
    """
    )
    from sre.compiler import evaluate_rule

    assert evaluate_rule(r, {"x": 1}).fired
    m = parse(
        """
    rule t
    when
    $x : T ( $x not in [ 0 ] )
    then
    end
    """
    )
    assert evaluate_rule(m, {"x": 1}).fired


def test_drl_comparisons_and_logic() -> None:
    s = """
    rule t
    when
    $x : T ( ( $x < 2 ) and ( $x > 0 ) and ( $x != 0 ) and ( $x == 1 ) and ( 1 < 2 ) and ( 1 >= 0 ) and ( 1 != 0 ) and ( 1 or 0 ) and not ( 0 == 1 ) and ( 1 and 1 ) )
    then
    end
    """
    p = parse(s)
    assert evaluate_rule(p, {"x": 1}).fired


def test_drl_not_contains_matches_list_call() -> None:
    s = """
    rule t
    when
    $s : T ( not ( $s contains "z" and $s matches "^a" and abs ( -1 ) in [ 1, 2 ] ) )
    then
    end
    """
    p = parse(s)
    assert evaluate_rule(p, {"s": "ab"}).fired


def test_drl_list_expr_and_abs_str() -> None:
    s = """
    rule t
    when
    $s : T ( ( abs ( 1 ) == 1 ) and ( 1 in [ 1, 2, 2 ] ) )
    then
    end
    """
    p = parse(s)
    assert evaluate_rule(p, {"s": 1}).fired


def test_drl_result_nested() -> None:
    s = """
    rule t
    when
    $q : T (1==1)
    then
    result.p.q = 1;
    end
    """
    p = parse(s)
    m = evaluate_rule(p, {"q": 0})
    assert m.action_output.get("p", {}).get("q") == 1


def test_drl_field_access_in_ast_only() -> None:
    fa = FieldAccess(base="o", field="f")
    assert evaluate_expr(fa, {"o": {"f": 9}}) == 9


def test_evaluate_expr_not_list_in() -> None:
    b = A.Literal(1)
    assert evaluate_expr(Not(b), {"x": 1}) is False
    assert evaluate_expr(
        InExpr(Identifier("x"), ListExpr((Literal(1), Literal(2))), False),
        {"x": 1},
    )
    with pytest.raises(ValueError):
        evaluate_expr(
            CallExpr("nope", (Literal(1),)), {"x": 1}
        )


def test_drl_call_abs_nonnum() -> None:
    s = "rule t when $a : T ( abs ( 1 ) == 1 ) then end"
    p = parse(s)
    # abs on string: returns v if not int|float
    s2 = "rule t2 when $a : T ( abs ( 1.5 ) < 2 ) then end"
    p2 = parse(s2)
    assert evaluate_rule(p, {"a": 0}).fired
    assert evaluate_rule(p2, {"a": 0}).fired


def test_get_id_result_dotted() -> None:
    p = parse("rule t when $a : T (1==1) then end")
    from sre.compiler import evaluate_rule
    m = evaluate_rule(
        p,
        {"a": 1, "result": {"p": {"q": 2}}},
    )
    m  # not fired? rule when 1==1 
    s = """
    rule t
    when
    $a : T ( result.p.q == 2 )
    then
    end
    """
    p2 = parse(s)
    assert not evaluate_rule(p2, {"a": 1, "result": {"p": {"q": 1}}}).fired

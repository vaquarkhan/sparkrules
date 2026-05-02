from sparkrules.compiler.discrimination import _freeze_expr
from sparkrules.parser import ast as A
from sparkrules.parser import parse
from sparkrules.parser.ast import BinaryOperator


def test_freeze_expr_covers_leaf_and_compound_patterns() -> None:
    snippets = (
        "$t:X( not false )",
        "$t:X( true and false )",
        "$t:X( abs( 3 ) >= 3 )",
    )
    for body in snippets:
        ast = parse(f"rule r when\n{body}\nthen end\n")
        c = ast.when[0].constraint
        assert c is not None
        assert _freeze_expr(c) is not None

    _freeze_expr(A.Identifier("z"))
    _freeze_expr(A.ListExpr((A.Literal(1), A.Literal(2))))
    _freeze_expr(A.Not(A.Literal(False)))
    _freeze_expr(A.InExpr(A.Literal(1), A.ListExpr((A.Literal(1), A.Literal(2))), False))
    _freeze_expr(A.FieldAccess("person", "age"))
    _freeze_expr(A.CallExpr("abs", (A.Literal(-9),)))
    _freeze_expr(A.BinaryOp(BinaryOperator.EQ, A.Literal(1), A.Literal(2)))

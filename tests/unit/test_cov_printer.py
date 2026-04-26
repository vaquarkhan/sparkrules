from __future__ import annotations

from sre.model.rule import DEFAULT_AGENDA_GROUP
from sre.parser import parse, print_ast
from sre.parser.ast import (
    Action,
    BinaryOp,
    BinaryOperator,
    FactPattern,
    FieldAccess,
    Literal,
    RuleAst,
)


def test_print_parsed_rule_roundtrip_shape() -> None:
    s = r"""
rule "my rule"
    salience 10
    agenda_group "OTHER"
    activation_group "A1"
    pass p1
    group_by [ "g1" ]
    reason_codes [ "R1" ]
when
$t : T ( $t.x == 1 ) and $u : U ( true )
then
result.x = 1;
end
"""
    r = parse(s)
    out = print_ast(r)
    assert "salience 10" in out
    assert "agenda_group" in out
    assert "group_by" in out
    assert "reason_codes" in out
    assert "when" in out and "then" in out


def test_printer_literals_and_field_access_fallback() -> None:
    r = RuleAst(
        name="r",
        salience=0,
        agenda_group=DEFAULT_AGENDA_GROUP,
        activation_group=None,
        pass_name=None,
        group_by=(),
        reason_codes=(),
        when=(
            FactPattern(
                "t",
                "T",
                BinaryOp(
                    BinaryOperator.EQ,
                    FieldAccess("a", "b"),
                    Literal("s p a c e"),
                ),
            ),
        ),
        then=(Action("out", Literal(True)),),
    )
    t = print_ast(r)
    assert "true" in t
    assert "s p a c e" in t or '"' in t

from sparkrules.parser import parse, print_ast
from sparkrules.parser.parser import DrlParser


def test_parse_minimal_and_round_trip() -> None:
    src = """
rule r1
when
$t : T ( $t.x == 1 )
then
result.x = 1;
end
"""
    r = parse(src)
    assert r.name == "r1"
    s2 = print_ast(r)
    r2 = parse(s2)
    assert r2.name == r.name
    assert len(r2.then) == len(r.then)


def test_parse_error_unresolved() -> None:
    src = """
rule bad
when
$t : T ( $y.x == 1 )
then
result.x = 1;
end
"""
    p = DrlParser()
    try:
        p.parse(src)
    except Exception as e:
        assert "unresolved" in str(e).lower() or e.__class__.__name__ == "ParseError"
    else:
        raise AssertionError("expected error")

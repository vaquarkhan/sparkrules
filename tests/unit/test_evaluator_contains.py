"""CONTAINS operator: collection membership vs string substring."""

from __future__ import annotations

from sre.compiler import evaluate_rule
from sre.parser import parse


def test_contains_list_is_membership_not_substring() -> None:
    drl = """
rule r
when
$t : T ( $t.items contains 2 )
then
result.ok = true;
end
"""
    r = parse(drl)
    m = evaluate_rule(r, {"t": {"items": [10, 20, 30]}})
    assert m.fired is False
    m2 = evaluate_rule(r, {"t": {"items": [2, 3]}})
    assert m2.fired is True


def test_contains_string_still_substring() -> None:
    drl = """
rule r
when
$t : T ( $t.label contains "foo" )
then
result.ok = true;
end
"""
    r = parse(drl)
    assert evaluate_rule(r, {"t": {"label": "food"}}).fired is True

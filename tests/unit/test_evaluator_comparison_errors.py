"""Comparison / binding edge cases in the DRL evaluator."""

from __future__ import annotations

import pytest

from sparkrules.compiler import RuleEvaluationError, evaluate_rule
from sparkrules.parser import parse


def test_compare_missing_binding_raises_rule_evaluation_error_not_typeerror() -> None:
    drl = """
rule r
when
$t : T ( $t.amount >= 100 )
then
result.ok = true;
end
"""
    r = parse(drl)
    with pytest.raises(RuleEvaluationError) as ei:
        evaluate_rule(r, {"amount": 5000})
    assert ei.value.code == "UNBOUND_OR_NULL"
    assert "fact" in str(ei.value).lower() or "t" in str(ei.value)


def test_compare_works_when_fact_is_shaped_correctly() -> None:
    drl = """
rule r
when
$t : T ( $t.amount >= 100 )
then
result.ok = true;
end
"""
    r = parse(drl)
    m = evaluate_rule(r, {"t": {"amount": 5000}})
    assert m.fired is True

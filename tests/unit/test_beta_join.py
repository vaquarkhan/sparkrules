from sparkrules.compiler.beta_join import (
    dual_pattern_rule_names,
    eligible_dual_join_names,
    refine_eligibility_with_beta_join,
)
from sparkrules.compiler.discrimination import DiscriminationNetwork
from sparkrules.parser import parse_rules
from sparkrules.runtime.rule_chain import ChainExecutionPolicy, run_rule_chain


def test_dual_pattern_names_and_join_eligibility() -> None:
    drl = (
        "rule j when $x : X ( true ) and $y : Y ( $y.score > 5 ) "
        "then result.ok = true; end"
    )
    rules = parse_rules(drl)
    assert "j" in dual_pattern_rule_names(rules)

    eligible = eligible_dual_join_names(rules, {"x": {}, "y": {"score": 10}})
    assert "j" in eligible

    not_ok = eligible_dual_join_names(rules, {"x": {}, "y": {"score": 1}})
    assert "j" not in not_ok


def test_beta_join_predicate_eval_exceptions_ignored() -> None:
    drl = "rule bad when $a : A ( true ) and $b : B ( typo() ) then end"
    rules = parse_rules(drl)
    out = eligible_dual_join_names(rules, {"a": {}, "b": {"nope": 1, "zero": 0}})
    assert "bad" not in out


def test_refine_eligibility_shrinks_dual_pattern_rules() -> None:
    """Dual-pattern ASTs are wildcard alpha-eligible; beta join may still drop them."""
    drl_only = "rule dj when $a : A ( true ) and $b : B ( $b.flag == true ) then end"
    rules = parse_rules(drl_only)
    base = frozenset({r.name for r in rules})
    refined = refine_eligibility_with_beta_join(base, rules, {"a": {}, "b": {"flag": False}})
    assert refined == frozenset()


def test_beta_join_chain_skips_dual_when_second_pattern_fails() -> None:
    drl = """
rule hi salience 10 when $t : T ( $t.v > 10 ) then result.x = "hi"; end
rule dj salience 5 when $a : A ( true ) and $b : B ( $b.flag == true ) then result.x = "dj"; end
"""
    rules = parse_rules(drl)
    dn = DiscriminationNetwork.from_asts(rules)
    work = {"t": {"v": 20}, "a": {}, "b": {"flag": False}}
    cr = run_rule_chain(rules, work, ChainExecutionPolicy(stop_on_decline=False), discrimination=dn)
    dj_steps = [s for s in cr.steps if s.rule_name == "dj"]
    assert dj_steps and dj_steps[0].skipped and dj_steps[0].skip_reason == "discrimination_alpha"

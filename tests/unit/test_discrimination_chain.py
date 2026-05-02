from sparkrules.compiler.discrimination import DiscriminationNetwork
from sparkrules.parser import parse_rules
from sparkrules.runtime.rule_chain import run_rule_chain


def test_rule_chain_skips_rules_failing_discrimination_alpha() -> None:
    drl = """
rule hi salience 10 when $t : T ( $t.v > 10 ) then result.pick = "hi"; end
rule lo salience 5 when $t : T ( $t.v < 2 ) then result.pick = "lo"; end
"""
    rules = parse_rules(drl)
    dn = DiscriminationNetwork.from_asts(rules)
    cr = run_rule_chain(rules, {"t": {"v": 1}}, discrimination=dn)
    assert any(s.rule_name == "hi" and s.skipped for s in cr.steps)
    assert any(s.rule_name == "lo" and s.fired for s in cr.steps)


def test_discrimination_share_alpha_evaluation() -> None:
    dn = DiscriminationNetwork.build(
        {
            "k1": "rule z1 when $x : X ( $x.a == 3 ) then end",
            "k2": "rule z2 when $x : X ( $x.a == 3 ) then end",
        }
    )
    before = dn.alpha_eval_counter
    dn.eligible_rule_names({"x": {"a": 3}})
    assert dn.alpha_eval_counter == before + 1


def test_discrimination_eligibility_ignores_predicate_eval_errors() -> None:
    dn = DiscriminationNetwork.build(
        {"k": "rule n when $z : Z ( $z.n > 10 ) then end"},
    )
    assert "n" not in dn.eligible_rule_names({})

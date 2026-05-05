from sparkrules.compiler.discrimination import DiscriminationNetwork


def test_multi_pattern_rules_are_always_eligible_via_wildcards() -> None:
    dn = DiscriminationNetwork.build(
        {
            "k": ("rule mw when $t : T ( true ) and $u : T ( true ) then end\n"),
        }
    )
    assert "mw" in dn.eligible_rule_names({})


def test_empty_constraint_patterns_are_always_eligible() -> None:
    dn = DiscriminationNetwork.build({"k": "rule c when $t : E() then end\n"})
    assert "c" in dn.eligible_rule_names({})

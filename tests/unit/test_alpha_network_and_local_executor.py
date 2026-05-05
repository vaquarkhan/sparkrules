"""Tests for Alpha Network (Req 3) and LocalRuleExecutor (Req 9)."""

from __future__ import annotations

from sparkrules.compiler.alpha_network import (
    AlphaNetwork,
    AlphaNodeV2,
    RuleAlphaMapping,
    _flatten_and,
    _structural_hash,
)
from sparkrules.executor.local_executor import LocalRuleExecutor, RuleFire, ScoreResult
from sparkrules.parser import parse, parse_rules
from sparkrules.parser.ast import BinaryOp, BinaryOperator, Literal


# --- Alpha Network (Req 3) ---


DRL_OVERLAP = """
rule "r1" salience 10 when $t : T ( $t.x > 5 ) then result.a = 1; end
rule "r2" salience 5 when $t : T ( $t.x > 5 ) then result.b = 2; end
rule "r3" when $t : T ( $t.y == "yes" ) then result.c = 3; end
"""


def test_alpha_deduplicates_shared_predicates() -> None:
    """Req 3, AC 1+2: shared predicates evaluated once."""
    rules = parse_rules(DRL_OVERLAP)
    net = AlphaNetwork.from_rules(rules)
    # r1 and r2 share $t.x > 5 -> should be 2 unique alphas, 3 total
    assert net.unique_alphas == 2
    assert net.total_predicates == 3
    assert net.sharing_ratio >= 1.0


def test_alpha_evaluate_shared() -> None:
    """Req 3, AC 2: each alpha evaluated once per fact."""
    rules = parse_rules(DRL_OVERLAP)
    net = AlphaNetwork.from_rules(rules)
    result = net.evaluate({"t": {"x": 10, "y": "yes"}})
    assert result["r1"] is True
    assert result["r2"] is True
    assert result["r3"] is True
    # The shared alpha ($t.x > 5) should have been evaluated only once
    shared_node = [n for n in net.nodes.values() if len(n.rule_names) > 1]
    assert len(shared_node) == 1
    assert shared_node[0].eval_count == 1


def test_alpha_evaluate_not_fired() -> None:
    rules = parse_rules(DRL_OVERLAP)
    net = AlphaNetwork.from_rules(rules)
    result = net.evaluate({"t": {"x": 3, "y": "no"}})
    assert result["r1"] is False
    assert result["r2"] is False
    assert result["r3"] is False


def test_alpha_wildcard_rules() -> None:
    """Rules with no constraint or multi-fact are wildcards (always eligible)."""
    drl = """
rule "wild" when $t : T ( true ) then end
rule "normal" when $t : T ( $t.x > 5 ) then end
"""
    rules = parse_rules(drl)
    net = AlphaNetwork.from_rules(rules)
    result = net.evaluate({"t": {"x": 3}})
    assert result["wild"] is True  # wildcard always fires
    assert result["normal"] is False


def test_alpha_multi_fact_wildcard() -> None:
    drl = 'rule "multi" when $a : A ( true ) and $b : B ( true ) then end'
    rules = parse_rules(drl)
    net = AlphaNetwork.from_rules(rules)
    result = net.evaluate({})
    assert result["multi"] is True  # multi-fact = wildcard


def test_alpha_and_chain_flattening() -> None:
    """Req 3, AC 1: AND-chains flattened into atomic predicates."""
    drl = 'rule "r" when $t : T ( $t.x > 5 and $t.y < 10 ) then end'
    rules = parse_rules(drl)
    net = AlphaNetwork.from_rules(rules)
    assert net.unique_alphas == 2  # two atomic predicates
    assert net.total_predicates == 2


def test_alpha_and_chain_partial_match() -> None:
    drl = 'rule "r" when $t : T ( $t.x > 5 and $t.y < 10 ) then end'
    rules = parse_rules(drl)
    net = AlphaNetwork.from_rules(rules)
    # x > 5 is True, y < 10 is False -> rule should not fire
    result = net.evaluate({"t": {"x": 10, "y": 20}})
    assert result["r"] is False


def test_alpha_sharing_ratio() -> None:
    """Req 3, AC 5: sharing ratio >= 2.0 for overlapping packs."""
    drl = "\n".join(f'rule "r{i}" when $t : T ( $t.score > 600 ) then end' for i in range(10))
    rules = parse_rules(drl)
    net = AlphaNetwork.from_rules(rules)
    assert net.sharing_ratio >= 2.0  # 10 predicates / 1 unique = 10.0


def test_alpha_empty_network() -> None:
    net = AlphaNetwork.from_rules([])
    assert net.unique_alphas == 0
    assert net.sharing_ratio == 0.0
    assert net.evaluate({}) == {}


def test_flatten_and() -> None:
    expr = BinaryOp(
        BinaryOperator.AND, Literal(1), BinaryOp(BinaryOperator.AND, Literal(2), Literal(3))
    )
    flat = _flatten_and(expr)
    assert len(flat) == 3


def test_structural_hash_deterministic() -> None:
    h1 = _structural_hash(Literal(42))
    h2 = _structural_hash(Literal(42))
    assert h1 == h2


# --- LocalRuleExecutor (Req 9) ---


DRL_LENDING = """
rule "credit_low" salience 20 reason_codes ["CR001"]
when $f : App( $f.score < 600 )
then result.decision = "decline"; result.reason = "low credit"; end

rule "credit_mid" salience 15 reason_codes ["CR002"]
when $f : App( $f.score < 700 )
then result.decision = "refer"; result.reason = "marginal credit"; end

rule "income_low" salience 10 reason_codes ["IN001"]
when $f : App( $f.income < 30000 )
then result.decision = "decline"; result.reason = "low income"; end

rule "dti_high" salience 5
when $f : App( $f.dti > 0.43 )
then result.decision = "refer"; result.reason = "high DTI"; end
"""


def test_local_executor_score() -> None:
    """Req 9, AC 1: score returns fired rules ordered by salience."""
    ex = LocalRuleExecutor.from_drl(DRL_LENDING)
    result = ex.score({"f": {"score": 550, "income": 25000, "dti": 0.5}})
    assert result.fired_any is True
    fired = [f for f in result.fires if f.fired]
    assert len(fired) >= 3  # credit_low, credit_mid, income_low, dti_high
    # Highest salience first
    assert fired[0].salience >= fired[-1].salience


def test_local_executor_merged_actions() -> None:
    """Highest salience wins for merged actions."""
    ex = LocalRuleExecutor.from_drl(DRL_LENDING)
    result = ex.score({"f": {"score": 550, "income": 25000, "dti": 0.5}})
    # credit_low (sal=20) should win for 'decision'
    assert result.merged_actions["decision"] == "decline"
    assert result.merged_actions["reason"] == "low credit"


def test_local_executor_no_fire() -> None:
    ex = LocalRuleExecutor.from_drl(DRL_LENDING)
    result = ex.score({"f": {"score": 800, "income": 100000, "dti": 0.2}})
    assert result.fired_any is False
    assert result.merged_actions == {}


def test_local_executor_batch() -> None:
    """Req 9, AC 3: batch evaluation."""
    ex = LocalRuleExecutor.from_drl(DRL_LENDING)
    facts = [
        {"f": {"score": 550, "income": 25000, "dti": 0.5}},
        {"f": {"score": 800, "income": 100000, "dti": 0.2}},
        {"f": {"score": 650, "income": 40000, "dti": 0.3}},
    ]
    results = ex.apply(facts)
    assert len(results) == 3
    assert results[0].fired_any is True
    assert results[1].fired_any is False
    assert results[2].fired_any is True  # credit_mid fires


def test_local_executor_reason_codes() -> None:
    ex = LocalRuleExecutor.from_drl(DRL_LENDING)
    result = ex.score({"f": {"score": 550, "income": 25000, "dti": 0.5}})
    codes = set()
    for f in result.fires:
        if f.fired:
            codes.update(f.reason_codes)
    assert "CR001" in codes
    assert "IN001" in codes


def test_local_executor_from_rulepack() -> None:
    from sparkrules.compiler.rulepack import RulePack

    pack = RulePack.from_drl(DRL_LENDING)
    ex = LocalRuleExecutor.from_rulepack(pack)
    result = ex.score({"f": {"score": 550, "income": 25000, "dti": 0.5}})
    assert result.fired_any is True


def test_local_executor_refresh_rules() -> None:
    """Req 23: hot-swap rules."""
    ex = LocalRuleExecutor.from_drl('rule "old" when $t : T ( $t.x > 5 ) then result.v = 1; end')
    r1 = ex.score({"t": {"x": 10}})
    assert r1.merged_actions.get("v") == 1

    ex.refresh_rules('rule "new" when $t : T ( $t.x > 100 ) then result.v = 2; end')
    r2 = ex.score({"t": {"x": 10}})
    assert r2.fired_any is False  # new rule doesn't fire on x=10


def test_local_executor_action_error_degrades() -> None:
    """Action errors degrade to None, not exceptions."""
    drl = 'rule "r" when $t : T ( true ) then result.v = $t.missing.deep; end'
    ex = LocalRuleExecutor.from_drl(drl)
    result = ex.score({"t": {}})
    assert result.fired_any is True
    assert result.merged_actions.get("v") is None

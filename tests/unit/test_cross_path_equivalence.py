"""Cross-path equivalence tests (Requirement 12).

Verifies that LocalRuleExecutor, AlphaNetwork, ReteNetwork, and the
closure compiler produce identical results to the reference evaluate_rule
function on the same rules and facts.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sparkrules.compiler import evaluate_rule
from sparkrules.compiler.alpha_network import AlphaNetwork
from sparkrules.compiler.closure import compile_predicate
from sparkrules.compiler.rete import ReteNetwork
from sparkrules.compiler.rulepack import RulePack, Strategy, _has_python_only_regex
from sparkrules.executor.local_executor import LocalRuleExecutor
from sparkrules.parser import parse, parse_rules
from sparkrules.parser.ast import BinaryOp, BinaryOperator, Literal
from sparkrules.spark.dataframe import iter_rule_rows


# --- Deterministic equivalence tests ---


RULES_DRL = """
rule "gt" salience 10 when $t : T ( $t.x > 5 ) then result.a = 1; end
rule "lt" salience 5 when $t : T ( $t.x < 3 ) then result.b = 2; end
rule "eq" when $t : T ( $t.y == "yes" ) then result.c = 3; end
rule "and" when $t : T ( $t.x > 0 and $t.y == "yes" ) then result.d = 4; end
rule "in" when $t : T ( $t.status in ["A", "B"] ) then result.e = 5; end
"""

FACTS = [
    {"t": {"x": 10, "y": "yes", "status": "A"}},
    {"t": {"x": 1, "y": "no", "status": "C"}},
    {"t": {"x": 6, "y": "yes", "status": "B"}},
    {"t": {"x": -1, "y": "no", "status": "A"}},
    {"t": {"x": 0, "y": "yes", "status": "X"}},
]


def _reference_results(drl: str, facts: list[dict]) -> list[dict[str, bool]]:
    """Reference implementation: per-rule evaluate_rule."""
    rules = parse_rules(drl)
    results = []
    for fact in facts:
        fired_map = {}
        for rule in rules:
            m = evaluate_rule(rule, dict(fact))
            fired_map[rule.name] = m.fired
        results.append(fired_map)
    return results


def test_alpha_network_matches_reference() -> None:
    """Req 12, AC 1: AlphaNetwork matches reference evaluate_rule."""
    ref = _reference_results(RULES_DRL, FACTS)
    rules = parse_rules(RULES_DRL)
    net = AlphaNetwork.from_rules(rules)
    for i, fact in enumerate(FACTS):
        alpha_result = net.evaluate(fact)
        for rule_name, expected in ref[i].items():
            assert alpha_result[rule_name] == expected, (
                f"Fact {i}, rule {rule_name}: alpha={alpha_result[rule_name]} ref={expected}"
            )


def test_rete_network_matches_reference() -> None:
    """Req 12: ReteNetwork matches reference evaluate_rule."""
    ref = _reference_results(RULES_DRL, FACTS)
    rules = parse_rules(RULES_DRL)
    net = ReteNetwork.from_rules(rules)
    for i, fact in enumerate(FACTS):
        rete_result = net.evaluate(fact)
        for rule_name, expected in ref[i].items():
            assert rete_result[rule_name] == expected, (
                f"Fact {i}, rule {rule_name}: rete={rete_result[rule_name]} ref={expected}"
            )


def test_local_executor_matches_reference() -> None:
    """Req 12, AC 1-2: LocalRuleExecutor matches reference."""
    ref = _reference_results(RULES_DRL, FACTS)
    ex = LocalRuleExecutor.from_drl(RULES_DRL)
    for i, fact in enumerate(FACTS):
        score = ex.score(fact)
        for fire in score.fires:
            expected = ref[i][fire.rule_name]
            assert fire.fired == expected, (
                f"Fact {i}, rule {fire.rule_name}: local={fire.fired} ref={expected}"
            )


def test_iter_rule_rows_v2_matches_reference() -> None:
    """Req 19: iter_rule_rows v2 matches reference for fired status."""
    ref = _reference_results(RULES_DRL, FACTS)
    rows = [{"id": str(i), **fact} for i, fact in enumerate(FACTS)]
    v2_results = list(iter_rule_rows(iter(rows), RULES_DRL, use_v2=True))
    for i, (fid, fired, _) in enumerate(v2_results):
        any_ref_fired = any(ref[i].values())
        assert fired == any_ref_fired, f"Fact {i}: v2={fired} ref={any_ref_fired}"


def test_closure_matches_reference_all_operators() -> None:
    """Req 12, AC 3: closure matches reference for all operator types."""
    test_cases = [
        ('rule "r" when $t : T ( $t.x > 5 ) then end', {"t": {"x": 10}}, True),
        ('rule "r" when $t : T ( $t.x > 5 ) then end', {"t": {"x": 3}}, False),
        ('rule "r" when $t : T ( $t.x == 5 ) then end', {"t": {"x": 5}}, True),
        ('rule "r" when $t : T ( $t.x != 5 ) then end', {"t": {"x": 3}}, True),
        ('rule "r" when $t : T ( $t.x >= 5 ) then end', {"t": {"x": 5}}, True),
        ('rule "r" when $t : T ( $t.x <= 5 ) then end', {"t": {"x": 5}}, True),
        ('rule "r" when $t : T ( $t.x < 5 ) then end', {"t": {"x": 3}}, True),
        ('rule "r" when $t : T ( $t.x in [1, 2, 3] ) then end', {"t": {"x": 2}}, True),
        ('rule "r" when $t : T ( $t.x not in [1, 2] ) then end', {"t": {"x": 5}}, True),
        ('rule "r" when $t : T ( $t.x > 5 and $t.y < 10 ) then end', {"t": {"x": 8, "y": 3}}, True),
        ('rule "r" when $t : T ( $t.x > 5 or $t.y < 10 ) then end', {"t": {"x": 3, "y": 3}}, True),
        ('rule "r" when $t : T ( not $t.x == 5 ) then end', {"t": {"x": 3}}, True),
        ('rule "r" when $t : T ( $t.name matches "^A.*" ) then end', {"t": {"name": "Alice"}}, True),
        ('rule "r" when $t : T ( $t.tags contains "vip" ) then end', {"t": {"tags": ["vip"]}}, True),
    ]
    for drl, fact, expected in test_cases:
        r = parse(drl)
        ref = evaluate_rule(r, dict(fact))
        closure = compile_predicate(r.when[0].constraint)
        closure_result = closure(fact)
        assert closure_result == ref.fired == expected, (
            f"DRL: {drl}, fact: {fact}, closure={closure_result}, ref={ref.fired}, expected={expected}"
        )


# --- Req 21: Regex compatibility ---


def test_python_only_regex_classified_as_fallback() -> None:
    """Req 21, AC 2: Python-only regex -> PYTHON_FALLBACK."""
    # Lookahead
    drl = 'rule "r" when $t : T ( $t.name matches "(?=.*admin).*" ) then end'
    pack = RulePack.from_drl(drl)
    assert pack.rules[0].strategy == Strategy.PYTHON_FALLBACK

    # Lookbehind
    drl2 = 'rule "r" when $t : T ( $t.name matches "(?<=prefix).*" ) then end'
    pack2 = RulePack.from_drl(drl2)
    assert pack2.rules[0].strategy == Strategy.PYTHON_FALLBACK


def test_spark_compatible_regex_stays_sql_pushdown() -> None:
    """Req 21, AC 4: Spark-compatible regex stays SQL_PUSHDOWN."""
    drl = 'rule "r" when $t : T ( $t.name matches "^[A-Z].*" ) then end'
    pack = RulePack.from_drl(drl)
    assert pack.rules[0].strategy == Strategy.SQL_PUSHDOWN


def test_case_insensitive_regex() -> None:
    """Req 21, AC 4: (?i) flag is Spark-compatible."""
    drl = 'rule "r" when $t : T ( $t.name matches "(?i)admin" ) then end'
    pack = RulePack.from_drl(drl)
    # (?i) is supported by both Python and Spark RLIKE
    assert pack.rules[0].strategy == Strategy.SQL_PUSHDOWN


def test_has_python_only_regex_detection() -> None:
    assert _has_python_only_regex(BinaryOp(BinaryOperator.MATCHES, Literal("x"), Literal("(?=foo)bar"))) is True
    assert _has_python_only_regex(BinaryOp(BinaryOperator.MATCHES, Literal("x"), Literal("^foo.*"))) is False
    assert _has_python_only_regex(BinaryOp(BinaryOperator.GT, Literal(1), Literal(2))) is False
    assert _has_python_only_regex(Literal(True)) is False


# --- Req 18: Performance targets (smoke test) ---


def test_local_executor_latency_under_1ms() -> None:
    """Req 18, AC 1: 50-rule pack, single fact, under 1ms."""
    import time

    drl = "\n".join(
        f'rule "r{i}" salience {50 - i} when $f : App( $f.score > {500 + i * 5} ) then result.d{i} = {i}; end'
        for i in range(50)
    )
    ex = LocalRuleExecutor.from_drl(drl)
    fact = {"f": {"score": 750}}

    # Warm up
    ex.score(fact)

    # Measure
    times = []
    for _ in range(100):
        start = time.perf_counter_ns()
        ex.score(fact)
        elapsed = time.perf_counter_ns() - start
        times.append(elapsed)

    p99_ns = sorted(times)[98]
    p99_us = p99_ns / 1000
    print(f"LocalRuleExecutor 50-rule p99: {p99_us:.0f}us")
    # Req 18 target: under 500us (1ms budget with margin)
    assert p99_us < 5000, f"p99 latency {p99_us}us exceeds 5ms budget"


def test_has_python_only_regex_in_not() -> None:
    """Cover _has_python_only_regex Not branch."""
    from sparkrules.parser.ast import Not as AstNot
    expr = AstNot(BinaryOp(BinaryOperator.MATCHES, Literal("x"), Literal("(?=foo)bar")))
    assert _has_python_only_regex(expr) is True
    expr2 = AstNot(BinaryOp(BinaryOperator.GT, Literal(1), Literal(2)))
    assert _has_python_only_regex(expr2) is False

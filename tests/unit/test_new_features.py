"""Tests for new features: parse caching, adverse-action notices, data profiling."""

from __future__ import annotations

from sparkrules.executor import RuleExecutor, build_adverse_action_notice, AdverseActionNotice
from sparkrules.executor.adverse_action import build_adverse_action_notice as _build
from sparkrules.dq.profile import profile_rows, DataProfile, FieldProfile, NumericStats, _percentile
from sparkrules.parser import parse, parse_rules


# --- Parse caching ---


def test_parse_returns_cached_object() -> None:
    drl = "rule cached when $t : T ( true ) then end"
    r1 = parse(drl)
    r2 = parse(drl)
    assert r1 is r2


def test_parse_rules_returns_cached_content() -> None:
    drl = "rule a when $t : T ( true ) then end\nrule b when $t : T ( true ) then end"
    r1 = parse_rules(drl)
    r2 = parse_rules(drl)
    assert len(r1) == 2
    assert len(r2) == 2
    # parse_rules returns a new list each time but from the same cached tuple
    assert r1[0].name == r2[0].name


def test_parse_different_drl_not_cached() -> None:
    r1 = parse("rule x when $t : T ( true ) then end")
    r2 = parse("rule y when $t : T ( true ) then end")
    assert r1 is not r2
    assert r1.name == "x"
    assert r2.name == "y"


# --- Adverse-action notices ---


DRL_DECLINE_SCORE = (
    'rule r1 reason_codes ["CR001", "CR002"] '
    'when $t : T ( $t.score < 600 ) then result.d = "decline"; end'
)
DRL_DECLINE_INCOME = (
    'rule r2 reason_codes ["IN001"] '
    'when $t : T ( $t.income < 30000 ) then result.d = "decline"; end'
)
DRL_NO_FIRE = 'rule r3 reason_codes ["NF001"] when $t : T ( $t.x > 9999 ) then end'


def test_adverse_action_aggregates_reason_codes() -> None:
    ex = RuleExecutor()
    fact = {"t": {"score": 550, "income": 25000, "x": 1}}
    results = [
        ex.run(fact, DRL_DECLINE_SCORE),
        ex.run(fact, DRL_DECLINE_INCOME),
    ]
    notice = build_adverse_action_notice(results, decision="decline", fact_id="app-1")
    assert isinstance(notice, AdverseActionNotice)
    assert notice.decision == "decline"
    assert notice.fact_id == "app-1"
    assert notice.rules_evaluated == 2
    assert notice.rules_fired == 2
    assert "CR001" in notice.all_reason_codes
    assert "CR002" in notice.all_reason_codes
    assert "IN001" in notice.all_reason_codes
    assert len(notice.principal_reasons) <= notice.max_reasons


def test_adverse_action_max_reasons_cap() -> None:
    ex = RuleExecutor()
    fact = {"t": {"score": 550, "income": 25000, "x": 1}}
    results = [
        ex.run(fact, DRL_DECLINE_SCORE),
        ex.run(fact, DRL_DECLINE_INCOME),
    ]
    notice = build_adverse_action_notice(results, max_reasons=2)
    assert len(notice.principal_reasons) == 2


def test_adverse_action_no_fired_rules() -> None:
    ex = RuleExecutor()
    fact = {"t": {"score": 800, "income": 100000, "x": 1}}
    results = [
        ex.run(fact, DRL_DECLINE_SCORE),
        ex.run(fact, DRL_NO_FIRE),
    ]
    notice = build_adverse_action_notice(results)
    assert notice.rules_fired == 0
    assert notice.principal_reasons == ()
    assert notice.all_reason_codes == ()


def test_adverse_action_to_dict() -> None:
    ex = RuleExecutor()
    fact = {"t": {"score": 550, "income": 25000, "x": 1}}
    results = [ex.run(fact, DRL_DECLINE_SCORE)]
    notice = build_adverse_action_notice(results, decision="refer", fact_id="f99")
    d = notice.to_dict()
    assert d["decision"] == "refer"
    assert d["fact_id"] == "f99"
    assert isinstance(d["principal_reasons"], list)
    assert isinstance(d["all_reason_codes"], list)


def test_adverse_action_deduplicates_codes() -> None:
    ex = RuleExecutor()
    fact = {"t": {"score": 550, "income": 25000, "x": 1}}
    # Run the same rule twice — codes should be deduplicated
    results = [
        ex.run(fact, DRL_DECLINE_SCORE),
        ex.run(fact, DRL_DECLINE_SCORE),
    ]
    notice = build_adverse_action_notice(results)
    assert notice.all_reason_codes == ("CR001", "CR002")


# --- Data profiling ---


def test_profile_empty_rows() -> None:
    p = profile_rows([])
    assert p.total_rows == 0
    assert p.total_fields == 0
    assert p.fields == ()


def test_profile_basic_numeric() -> None:
    rows = [{"age": 20}, {"age": 30}, {"age": 40}]
    p = profile_rows(rows)
    assert p.total_rows == 3
    assert p.total_fields == 1
    f = p.fields[0]
    assert f.field_name == "age"
    assert f.completeness == 1.0
    assert f.null_count == 0
    assert f.is_numeric is True
    assert f.numeric_stats is not None
    assert f.numeric_stats.mean == 30.0
    assert f.numeric_stats.min_val == 20.0
    assert f.numeric_stats.max_val == 40.0


def test_profile_with_nulls() -> None:
    rows = [{"x": 1}, {"x": None}, {"x": 3}, {"x": None}]
    p = profile_rows(rows)
    f = p.fields[0]
    assert f.null_count == 2
    assert f.completeness == 0.5
    assert f.numeric_stats is not None
    assert f.numeric_stats.count == 2


def test_profile_categorical() -> None:
    rows = [{"color": "red"}, {"color": "blue"}, {"color": "red"}, {"color": "green"}]
    p = profile_rows(rows)
    f = p.fields[0]
    assert f.is_numeric is False
    assert f.numeric_stats is None
    assert f.distinct_count == 3
    assert f.uniqueness == 0.75
    assert f.top_values[0] == ("red", 2)


def test_profile_mixed_fields() -> None:
    rows = [
        {"age": 25, "name": "Alice", "score": 90.5},
        {"age": 35, "name": "Bob", "score": 85.0},
        {"age": 45, "name": "Alice", "score": None},
    ]
    p = profile_rows(rows)
    assert p.total_fields == 3
    by_name = {f.field_name: f for f in p.fields}
    assert by_name["age"].is_numeric is True
    assert by_name["name"].is_numeric is False
    assert by_name["score"].null_count == 1


def test_profile_specific_fields() -> None:
    rows = [{"a": 1, "b": 2, "c": 3}]
    p = profile_rows(rows, fields=["a", "c"])
    assert p.total_fields == 2
    names = [f.field_name for f in p.fields]
    assert "a" in names
    assert "c" in names
    assert "b" not in names


def test_profile_to_dict() -> None:
    rows = [{"x": 10}, {"x": 20}]
    p = profile_rows(rows)
    d = p.to_dict()
    assert d["total_rows"] == 2
    assert len(d["fields"]) == 1
    assert "stats" in d["fields"][0]
    assert d["fields"][0]["stats"]["mean"] == 15.0


def test_profile_top_n() -> None:
    rows = [{"v": c} for c in "aaabbbccddddee"]
    p = profile_rows(rows, top_n=3)
    f = p.fields[0]
    assert len(f.top_values) == 3
    assert f.top_values[0][0] == "d"  # most frequent


def test_percentile_helper() -> None:
    assert _percentile([], 0.5) == 0.0
    assert _percentile([10.0], 0.5) == 10.0
    assert _percentile([10.0, 20.0, 30.0], 0.5) == 20.0


# --- Coverage: __init__._check_api_extras ---


def test_check_api_extras_callable() -> None:
    from sparkrules import _check_api_extras

    _check_api_extras()  # should not raise


# --- Coverage: two_pass binding-wrapper fallback ---


def test_two_pass_group_by_nested_fact() -> None:
    """Bug 20 fix: group_by resolves keys inside binding wrappers."""
    from sparkrules.runtime.two_pass import TwoPassOrchestrator

    P1 = """
rule p1
when
$t : T ( true )
then
result.x = 1;
end
"""
    P2 = """
rule p2
when
$t : T ( true )
then
result.y = 1;
end
"""
    orch = TwoPassOrchestrator(P1, P2, group_by=("region",))
    rows = [
        {"t": {"region": "US"}},
        {"t": {"region": "EU"}},
        {"t": {"region": "US"}},
    ]
    out = orch.run(rows)
    by_key = {a.key: int(a.value) for a in out.aggregates}
    assert by_key[("US",)] == 2
    assert by_key[("EU",)] == 1

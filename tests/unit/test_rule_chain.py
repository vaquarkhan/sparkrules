from __future__ import annotations

import pytest

from sparkrules.compiler import evaluate_rule
from sparkrules.parser import parse, parse_rules
from sparkrules.parser.ast import ParseError
from sparkrules.runtime.rule_chain import ChainExecutionPolicy, run_rule_chain
from sparkrules.sim import RuleSimulator


def test_parse_stop_on_fire() -> None:
    r = parse("rule a stop_on_fire true when $t : T ( true ) then end")
    assert r.name == "a"
    assert r.stop_on_fire is True
    r2 = parse("rule b stop_on_fire false when $t : T ( true ) then end")
    assert r2.stop_on_fire is False


def test_parse_rules_multi_block() -> None:
    s = """
rule r1
when $a : T ( $a.x > 0 ) then
    result.p = 1;
end
rule r2
when $a : T ( true ) then
    result.q = 2;
end
"""
    rs = parse_rules(s)
    assert [x.name for x in rs] == ["r1", "r2"]


def test_chain_salience_and_stop_on_fire() -> None:
    drl = """
rule high salience 10
stop_on_fire true
when $t : T ( true ) then
    result.h = 1;
end
rule low salience 0
when $t : T ( true ) then
    result.extra = 1;
end
"""
    rs = parse_rules(drl)
    out = run_rule_chain(rs, {"t": {"x": 1}}, ChainExecutionPolicy(stop_on_decline=False))
    assert out.stop_reason and out.stop_reason.startswith("stop_on_fire:")
    assert "extra" not in out.final_action


def test_fire_max_stops_after_n_firings() -> None:
    drl = """
rule a salience 10
when $t : T ( true ) then
    result.tag = "a";
end
rule b salience 0
when $t : T ( true ) then
    result.tag = "b";
end
"""
    rs = parse_rules(drl)
    cr = run_rule_chain(rs, {"t": {}}, ChainExecutionPolicy(stop_on_decline=False, max_fires=1))
    assert cr.stop_reason == "fire_max"
    assert sum(1 for s in cr.steps if s.fired) == 1


def test_stop_on_decline() -> None:
    drl = """
rule a salience 10
when $t : T ( true ) then
    result.decision = "decline";
end
rule b salience 0
when $t : T ( true ) then
    result.extra = 1;
end
"""
    rs = parse_rules(drl)
    r = run_rule_chain(rs, {"t": {"x": 0}}, ChainExecutionPolicy(stop_on_decline=True))
    assert r.stop_reason == "stop_on_decline"
    assert len(r.steps) == 1


def test_activation_group_mutex() -> None:
    drl = """
rule first salience 10
activation_group "g"
when $t : T ( $t.x == 1 ) then
    result.who = "first";
end
rule second salience 5
activation_group "g"
when $t : T ( true ) then
    result.who = "second";
end
"""
    rs = parse_rules(drl)
    o = run_rule_chain(rs, {"T": {"x": 1}, "t": {"x": 1}})
    assert o.steps[0].fired
    assert o.steps[1].skipped
    assert o.final_action.get("who") == "first"


def test_simulator_run_chain() -> None:
    sim = RuleSimulator()
    drl = "rule a when $t : T ( true ) then end\nrule b when $t : T ( true ) then end"
    c = sim.run_chain(drl, {"t": {}})
    assert len(c.chain.steps) == 2


def test_agenda_group_first_match_mode() -> None:
    drl = """
rule r1 salience 10
agenda_group "auth"
when $t : T ( true ) then
    result.w = "r1";
end
rule r2 salience 5
agenda_group "auth"
when $t : T ( true ) then
    result.w = "r2";
end
"""
    o = run_rule_chain(
        parse_rules(drl),
        {"t": {}},
        ChainExecutionPolicy(agenda_group_modes={"auth": "first_match"}),
    )
    assert o.steps[0].fired is True
    assert o.steps[1].skipped is True
    assert o.steps[1].skip_reason == "agenda_group:first_match"


def test_agenda_group_first_failure_mode() -> None:
    drl = """
rule check1 salience 10
agenda_group "inclusion"
when $t : T ( false ) then
    result.ok = true;
end
rule check2 salience 0
agenda_group "inclusion"
when $t : T ( true ) then
    result.ok = true;
end
"""
    o = run_rule_chain(
        parse_rules(drl),
        {"t": {}},
        ChainExecutionPolicy(agenda_group_modes={"inclusion": "first_failure"}),
    )
    assert o.steps[0].fired is False
    assert o.steps[1].skipped is True
    assert o.steps[1].skip_reason == "agenda_group:first_failure"


def test_agenda_group_mode_invalid() -> None:
    with pytest.raises(ValueError, match="agenda group mode"):
        run_rule_chain(
            parse_rules("rule a agenda_group g when $t : T ( true ) then end"),
            {"t": {}},
            ChainExecutionPolicy(agenda_group_modes={"g": "bad_mode"}),
        )


def test_run_rule_chain_empty() -> None:
    o = run_rule_chain([], {"t": {}})
    assert o.steps == []


def test_carry_result_failed_when_preserves_result() -> None:
    r = parse("rule x when $t : T ( false ) then result.x = 1; end")
    m = evaluate_rule(r, {"t": {}, "result": {"p": 9}}, carry_result=True)
    assert not m.fired
    assert m.action_output.get("p") == 9


def test_parse_single_rule_trailing_tokens() -> None:
    with pytest.raises(ParseError, match="expected end of file"):
        parse("rule a when $t : T ( true ) then end rule b when $t : T ( true ) then end")


def test_parse_rules_not_rule() -> None:
    with pytest.raises(ParseError, match="expected 'rule' or end"):
        parse_rules("when $t : T ( true ) then end")


def test_stop_on_fire_parse_error() -> None:
    with pytest.raises(ParseError, match="expected true or false"):
        parse("rule a stop_on_fire when $t : T ( true ) then end")


def test_parse_activation_and_agenda_group_hyphen_keywords() -> None:
    drools_style = """
rule hyphen_act activation-group "g1" agenda-group "lab" when $t : T ( true ) then end
"""
    r = parse_rules(drools_style)[0]
    assert r.activation_group == "g1"
    assert r.agenda_group == "lab"

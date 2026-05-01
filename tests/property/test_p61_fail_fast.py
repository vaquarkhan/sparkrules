"""P61 — fail-fast / stop_on_fire determinism (Phase 2k)."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from hypo_settings import PROFILE

from sparkrules.parser import parse_rules
from sparkrules.runtime.rule_chain import run_rule_chain


BASE = """
rule gate salience 100
stop_on_fire true
when $t : T ( true ) then
result.n = 1;
end
rule follow salience 0
when $t : T ( true ) then
result.m = 2;
end
"""


@given(st.dictionaries(st.text(min_size=0, max_size=3), st.integers(), max_size=4))
@settings(parent=PROFILE)
def test_p61_deterministic_stop_on_fire(payload: dict) -> None:
    fact = {"t": {"x": 1, "extra": dict(payload)}}
    rs0 = parse_rules(BASE)
    a = run_rule_chain(rs0, fact)
    rs1 = parse_rules(BASE)
    b = run_rule_chain(rs1, fact)
    assert a.stop_reason == b.stop_reason
    assert a.final_action == b.final_action
    assert len(a.steps) == 1
    assert a.stop_reason == "stop_on_fire:gate"

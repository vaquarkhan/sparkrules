from __future__ import annotations

from sparkrules.sim import RuleSimulator


def test_shadow_mode_detects_drift() -> None:
    sim = RuleSimulator()
    a = 'rule a when $t : T ( true ) then result.decision = "approve"; end'
    b = 'rule b when $t : T ( true ) then result.decision = "decline"; end'
    out = sim.run_shadow(a, b, {"t": {}})
    assert out.primary.fired is True
    assert out.shadow.fired is True
    assert out.drifted is True
    assert out.drift_fields == ("decision",)


def test_shadow_mode_no_drift_when_equal_outputs() -> None:
    sim = RuleSimulator()
    a = 'rule a when $t : T ( true ) then result.decision = "approve"; end'
    b = 'rule b when $t : T ( true ) then result.decision = "approve"; end'
    out = sim.run_shadow(a, b, {"t": {}})
    assert out.drifted is False
    assert out.drift_fields == ()

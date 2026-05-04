from __future__ import annotations

from sparkrules.tools.shadow_parity_gate import shadow_parity_summary


def test_shadow_parity_summary_match_and_drift() -> None:
    a = {"x": 1}
    assert shadow_parity_summary(a, dict(a))["drifted"] is False
    assert shadow_parity_summary(a, {"x": 2})["drifted"] is True

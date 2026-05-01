"""TwoPassOrchestrator aggregates and per-group quota."""

from __future__ import annotations

from sparkrules.runtime.two_pass import TwoPassOrchestrator

P1 = """
rule p1
when
$t : T ( $t.ok == 1 )
then
result.eligible = 1;
end
"""
P2 = """
rule p2
when
$t : T ( true )
then
result.capped = 1;
end
"""


def test_aggregates_count_pass1_by_group() -> None:
    orch = TwoPassOrchestrator(P1, P2, group_by=("t.store",))
    rows = [
        {"t": {"ok": 1, "store": "A"}},
        {"t": {"ok": 1, "store": "A"}},
        {"t": {"ok": 1, "store": "B"}},
        {"t": {"ok": 0, "store": "B"}},
    ]
    out = orch.run(rows)
    assert len(out.aggregates) == 2
    by_key = {a.key: int(a.value) for a in out.aggregates}
    assert by_key[("A",)] == 2
    assert by_key[("B",)] == 1


def test_quota_per_group_limits_pass2() -> None:
    orch = TwoPassOrchestrator(P1, P2, group_by=(), quota_per_group=1)
    rows = [
        {"t": {"ok": 1}},
        {"t": {"ok": 1}},
    ]
    out = orch.run(rows)
    assert len(out.pass1_fired) == 2
    assert len(out.pass2_fired) == 1

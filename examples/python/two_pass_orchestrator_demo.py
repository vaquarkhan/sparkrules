"""Two-pass evaluation with optional ``group_by`` counts and per-group quota.

Uses :class:`sparkrules.runtime.two_pass.TwoPassOrchestrator` (Pass1 qualifies rows;
Pass2 runs on qualifiers only).

  python examples/python/two_pass_orchestrator_demo.py
"""

from __future__ import annotations

from sparkrules.runtime.two_pass import TwoPassOrchestrator


def main() -> None:
    p1 = 'rule "qualify" when $t : T ( $t.flag == true ) then end'
    p2 = 'rule "deep" when $t : T ( true ) then end'
    orch = TwoPassOrchestrator(
        pass1_drl=p1,
        pass2_drl=p2,
        group_by=("region",),
        quota_per_group=1,
    )
    rows = [
        {"t": {"flag": True, "region": "US"}, "region": "US"},
        {"t": {"flag": True, "region": "US"}, "region": "US"},
        {"t": {"flag": False, "region": "EU"}, "region": "EU"},
        {"t": {"flag": True, "region": "EU"}, "region": "EU"},
    ]
    res = orch.run(rows)
    print("pass1_fired:", res.pass1_fired)
    print("aggregates:", [(a.key, a.value) for a in res.aggregates])
    print("pass2_fired:", res.pass2_fired)


if __name__ == "__main__":
    main()

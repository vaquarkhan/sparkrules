from __future__ import annotations

from sre.sim import RuleSimulator


def test_coverage_analyzer_counts_and_rates() -> None:
    drl = """
rule r1
when $t : T ( $t.x == 1 ) then
result.a = true;
end
rule r2
when $t : T ( $t.y > 10 ) then
result.b = true;
end
"""
    facts = [{"t": {"x": 1, "y": 5}}, {"t": {"x": 0, "y": 20}}]
    out = RuleSimulator().analyze_coverage(drl, facts)
    assert out.total_facts == 2
    assert out.total_rules == 2
    assert out.covered_rules == 2
    by_name = {i.rule_name: i for i in out.items}
    assert by_name["r1"].fired_count == 1
    assert by_name["r1"].fire_rate == 0.5
    assert by_name["r2"].fired_count == 1
    assert by_name["r2"].fire_rate == 0.5


def test_coverage_analyzer_empty_facts() -> None:
    drl = "rule r when $t : T ( true ) then result.ok = true; end"
    out = RuleSimulator().analyze_coverage(drl, [])
    assert out.total_facts == 0
    assert out.total_rules == 1
    assert out.covered_rules == 0
    assert out.items[0].fire_rate == 0.0

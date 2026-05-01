"""Property tests P20–P38 (idea-brainstrom.md §7)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings, strategies as st

from hypo_settings import PROFILE

from sparkrules.compiler import evaluate_rule
from sparkrules.compiler.discrimination import DiscriminationNetwork
from sparkrules.model import (
    ColumnType,
    DecisionTable,
    HitPolicy,
    InputColumn,
    OutputColumn,
    Row,
    dt_from_json,
    dt_to_json,
    evaluate_decision_table,
)
from sparkrules.model.rule import now_utc
from sparkrules.runtime.batch import BatchEvaluator, RunRecord
from sparkrules.runtime.cache import DerivedColumnCache
from sparkrules.runtime.iceberg_store import IcebergLikeTable
from sparkrules.runtime.streaming import StreamingEvaluator, StreamingRuleRefresher
from sparkrules.runtime.two_pass import TwoPassOrchestrator
from sparkrules.parser import parse
from sparkrules.sim.ab import ABTestConfig, ABTestRunner, Variant
from sparkrules.sim.replay import MissingRuleSetVersionError, ReplayService
from sparkrules.sim.simulator import RuleSimulator
from sparkrules.executor.rule_executor import RuleExecutor

DRL_P1 = """
rule p1
when
$t : T ( $t.ok == 1 )
then
result.p1 = 1;
end
"""
DRL_P2 = """
rule p2
when
$t : T ( $t.ok == 1 )
then
result.p2 = 1;
end
"""
DRL_ERR_WHEN = """
rule a
when
$t : T ( 1==1 ) and
$u : U ( 1==1 )
then
result.r = 0;
end
"""
DRL_REASON = """
rule r1
    reason_codes [ "RC1", "RC2" ]
when
$z : T ( $z.n == 0 )
then
result.r = 1;
end
"""


def test_p20_shared_predicate_eval_count() -> None:
    """Feature: spark-rule-engine, Property 20: one evaluation per rule fire check.

    Validates: Req 13.2.
    """
    dn = DiscriminationNetwork.build(
        {
            "r1": "rule t when $x : T (1==1) then end",
            "r2": "rule t when $x : T (1==1) then end",
        }
    )
    c0 = dn.eval_counter
    dn.evaluate("r1", {"x": 0})
    assert dn.eval_counter == c0 + 1
    dn.evaluate("r2", {"x": 0})
    assert dn.eval_counter == c0 + 2


def test_p21_cache_cleared_at_end() -> None:
    """Feature: spark-rule-engine, Property 21: derived column cache can be dropped.

    Validates: Req 15.2.
    """
    c = DerivedColumnCache()
    c.put((0, "c"), 1)
    assert c.size() == 1
    c.clear()
    assert c.size() == 0


@given(age_s=st.integers(min_value=1, max_value=10_000))
@settings(parent=PROFILE)
def test_p22_state_ttl(age_s: int) -> None:
    """Feature: spark-rule-engine, Property 22: TTL expires after window.

    Validates: Req 17.3.
    """
    e = StreamingEvaluator(timedelta(seconds=30))
    t0 = datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert e.check_ttl(t0, None) is True
    last = t0 - timedelta(seconds=age_s)
    assert e.check_ttl(t0, last) is (age_s > 30)


def test_p23_compile_fail_keeps_prior() -> None:
    """Feature: spark-rule-engine, Property 23: failed compile does not advance ref.

    Validates: Req 18.3.
    """
    r = StreamingRuleRefresher(current="v0")

    def boom() -> object:
        raise RuntimeError("compile failed")

    out = r.maybe_refresh("v1", recompile=boom)
    assert out is None
    assert r.current == "v0"

    ok = [0]

    def good() -> object:
        ok[0] += 1
        return object()

    r2 = r.maybe_refresh("v1", recompile=good)
    assert r2 == "v1"
    assert r.current == "v1"
    assert ok[0] == 1


def test_p24_simulator_never_persists() -> None:
    """Feature: spark-rule-engine, Property 24: simulation does not append storage.

    Validates: Req 19.1.
    """
    sim = RuleSimulator()
    sim.run(
        "rule r when $t : T (1==1) then end",
        {"t": 1},
    )
    assert sim._persist == []


def test_p25_ab_deterministic() -> None:
    """Feature: spark-rule-engine, Property 25: A/B hash assignment stable.

    Validates: Req 20.2, 20.3.
    """
    cfg = ABTestConfig("k", (Variant("A", 1), Variant("B", 1)))
    r = ABTestRunner()
    for _ in range(5):
        assert r.assign("user-42", cfg) == r.assign("user-42", cfg)


def test_p26_decision_table_json_rt() -> None:
    """Feature: spark-rule-engine, Property 26: decision table JSON round-trip.

    Validates: Req 23.3.
    """
    dt = DecisionTable(
        "dt",
        HitPolicy.FIRST,
        (InputColumn("i1", "a", ColumnType.STRING, "=="),),
        (OutputColumn("o1", "b", ColumnType.STRING),),
        (Row(("x", "y"), 0),),
    )
    s = dt_to_json(dt)
    dt2 = dt_from_json(s)
    assert dt2.name == dt.name
    assert evaluate_decision_table(dt, {"a": "x"}) == evaluate_decision_table(
        dt2, {"a": "x"}
    )


def test_p27_error_isolation_per_run() -> None:
    """Feature: spark-rule-engine, Property 27: one path errors, another succeeds.

    Validates: Req 24.1.
    """
    ex = RuleExecutor()
    bad = ex.run({"t": {"x": 1}}, DRL_ERR_WHEN, fact_id="1")
    assert bad.error_class is not None
    g2 = ex.run(
        {"t": {"x": 1}},
        "rule g when $t : T ( $t.x == 1 ) then result.x = 1; end",
        fact_id="3",
    )
    assert g2.fired and g2.error_class is None


def test_p28_pass2_sees_only_pass1_qualified() -> None:
    """Feature: spark-rule-engine, Property 28: pass-2 input ⊆ pass-1 qualified.

    Validates: Req 26.6, 26.7.
    """
    orch = TwoPassOrchestrator(
        DRL_P1,
        DRL_P2,
    )
    rows: list[dict] = [
        {"t": {"ok": 0}},
        {"t": {"ok": 1}},
    ]
    r = orch.run(rows)
    assert r.pass1_fired
    assert len(r.pass2_fired) <= len([x for x in rows if x["t"]["ok"] == 1])


def test_p29_pass2_after_pass1_aggregates() -> None:
    """Feature: spark-rule-engine, Property 29: two-pass order pass1 then pass2.

    Validates: Req 26.3-26.5.
    """
    orch = TwoPassOrchestrator(DRL_P1, DRL_P2)
    r = orch.run([{"t": {"ok": 1}}])
    assert r.pass1_fired
    assert r.pass2_fired


def test_p30_pos_batch_determinism() -> None:
    """Feature: spark-rule-engine, Property 30: batch run determinism (POS proxy).

    Validates: Req 27.4, 27.5.
    """
    be = BatchEvaluator("rule t when $t : T (1==1) then result.s = 1; end")
    rows = ({"t": 1, "id": "a"}, {"t": 1, "id": "b"})
    a, ra = be.run(rows)
    b, rb = be.run(rows)
    assert [x.fired for x in a] == [x.fired for x in b]
    assert ra.facts_processed == rb.facts_processed


def test_p31_auth_determinism() -> None:
    """Feature: spark-rule-engine, Property 31: same facts → same A/B arm.

    Validates: Req 28.4.
    """
    cfg = ABTestConfig("auth", (Variant("on", 1), Variant("off", 1)))
    r = ABTestRunner()
    assert r.assign("session-9", cfg) == r.assign("session-9", cfg)


def test_p32_underwriting_flow_determinism() -> None:
    """Feature: spark-rule-engine, Property 32: identical inputs → same rule outcome.

    Validates: Req 30.3.
    """
    ex = RuleExecutor()
    drl = "rule u when $a : T ( $a == 1 ) then result.approved = 1; end"
    a = ex.run({"a": 1}, drl, fact_id="1")
    b = ex.run({"a": 1}, drl, fact_id="2")
    assert a.fired == b.fired
    assert a.action_output == b.action_output


def test_p33_mode_parity_row() -> None:
    """Feature: spark-rule-engine, Property 33: batch row vs direct eval parity.

    Validates: Req 31.3.
    """
    drl = "rule t when $t : T (1==1) then end"
    be = BatchEvaluator(drl)
    m = {"t": 1, "id": 0}
    fr_list, _ = be.run([m])
    d = parse(drl)
    m2 = evaluate_rule(d, {"t": 1})
    assert fr_list[0].fired is m2.fired


def test_p34_acid_snapshot_layers() -> None:
    """Feature: spark-rule-engine, Property 34: new writes do not change old snapshot.

    Validates: Req 32.2.
    """
    t = IcebergLikeTable("T", {"x": int})
    s0 = t.append([{"x": 1}])
    t.append([{"x": 2}])
    first = t.snapshot(s0)
    assert len(first) == 1 and first[0]["x"] == 1


def test_p35_snapshot_read_idempotent() -> None:
    """Feature: spark-rule-engine, Property 35: repeated snapshot read is stable.

    Validates: Req 32.7.
    """
    t = IcebergLikeTable("T", {"x": int})
    t.append([{"x": 1}])
    sid = t.current_snapshot_id()
    a = t.snapshot(sid)
    b = t.snapshot(sid)
    assert a == b


def test_p36_replay_version_gate() -> None:
    """Feature: spark-rule-engine, Property 36: replay pins rule_set_version.

    Validates: Req 33.3, 27.4, 29.4.
    """
    t0, t1 = now_utc(), now_utc()
    run = RunRecord(
        run_id="r-1",
        mode="BATCH",
        input_table_name="F",
        input_snapshot_id=0,
        rule_set_version="v9",
        config_fingerprint="c",
        start_ts=t0,
        end_ts=t1,
        facts_processed=1,
        rules_fired=0,
        rules_errored=0,
        status="OK",
        error_class=None,
        error_message=None,
    )
    r = ReplayService()
    with pytest.raises(MissingRuleSetVersionError):
        r.replay(run, "v8")
    assert r.replay(run, "v9") == "r-1"


def test_p37_reason_subset() -> None:
    """Feature: spark-rule-engine, Property 37: reason codes ⊆ declared on rule.

    Validates: Req 34.2, 34.6.
    """
    rast = parse(DRL_REASON)
    assert rast.reason_codes == ("RC1", "RC2")
    ex = RuleExecutor()
    fr = ex.run({"z": {"n": 0}}, DRL_REASON)
    assert set(fr.reason_codes) == {"RC1", "RC2"}


def test_p38_explanation_fields_populated() -> None:
    """Feature: spark-rule-engine, Property 38: result captures bound + action.

    Validates: Req 34.3.
    """
    ex = RuleExecutor()
    fr = ex.run(
        {"z": {"n": 0}},
        "rule t when $z : T ( $z.n == 0 ) then result.why = 1; end",
    )
    assert fr.fired
    assert "why" in fr.action_output
    assert isinstance(fr.bound_fields, dict)


# ---- Note: P37 duplicate test name fixed — merge into one file with single P37
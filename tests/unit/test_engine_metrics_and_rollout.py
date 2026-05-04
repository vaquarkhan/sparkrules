"""Tests for Req 30–31 engine metrics and rollout helpers."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from sparkrules.compiler.rulepack import RulePack, Strategy, classify_rule_with_rationale
from sparkrules.compiler.translator import TranslationError
from sparkrules.parser import parse
from sparkrules.executor.local_executor import LocalRuleExecutor
from sparkrules.runtime.engine_metrics import (
    engine_metrics_enabled,
    max_rulepack_bytes_from_environ,
    record_score_completed,
    record_translation_failure,
    reset_engine_metrics,
    set_engine_metrics_enabled,
    snapshot_engine_metrics,
)
from sparkrules.runtime.rollout import (
    RolloutConfig,
    compare_v1_v2_single_rule_fired,
    rollout_config_from_environ,
)


@pytest.fixture(autouse=True)
def _metrics_reset() -> None:
    reset_engine_metrics()
    set_engine_metrics_enabled(None)
    yield
    reset_engine_metrics()
    set_engine_metrics_enabled(None)


def test_engine_metrics_default_disabled() -> None:
    assert engine_metrics_enabled() is False


def test_set_engine_metrics_forced() -> None:
    set_engine_metrics_enabled(True)
    assert engine_metrics_enabled() is True
    set_engine_metrics_enabled(False)
    assert engine_metrics_enabled() is False


def test_rulepack_classified_and_local_score_snapshot() -> None:
    set_engine_metrics_enabled(True)
    drl = 'rule "a" when $t : T ( $t.x > 1 ) then result.y = 1; end'
    ex = LocalRuleExecutor.from_drl(drl)
    ex.score({"t": {"x": 5}})
    snap = snapshot_engine_metrics()
    assert snap["evaluations_total"] == 1
    assert snap["rows_evaluated_total"] == 1
    assert snap["classification_rule_hits"]["SQL_PUSHDOWN"] == 1
    assert snap["rules_fired_total"] >= 1
    assert snap["executor_tags"]["v2_local"] == 1


def test_record_score_completed_with_fires_by_strategy() -> None:
    set_engine_metrics_enabled(True)
    reset_engine_metrics()
    pack = RulePack.from_drl("rule r when $t : T ( true ) then end")
    reset_engine_metrics()
    record_score_completed(
        latency_seconds=0.002,
        rows=10,
        pack=pack,
        executor_tag="test",
        fires_by_strategy={"SQL_PUSHDOWN": 25},
    )
    snap = snapshot_engine_metrics()
    assert snap["rules_fired_total"] == 25
    assert snap["rules_fired_by_strategy"]["SQL_PUSHDOWN"] == 25


def test_max_rulepack_bytes_env_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_MAX_RULEPACK_BYTES", "not-int")
    assert max_rulepack_bytes_from_environ() is None


def test_max_rulepack_bytes_env_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_MAX_RULEPACK_BYTES", "8192")
    assert max_rulepack_bytes_from_environ() == 8192


def test_engine_metrics_enabled_via_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_ENGINE_METRICS", "1")
    set_engine_metrics_enabled(None)
    assert engine_metrics_enabled() is True


def test_record_score_completed_skips_when_metrics_disabled() -> None:
    set_engine_metrics_enabled(False)
    reset_engine_metrics()
    pack = RulePack.from_drl("rule r when $t : T ( true ) then end")
    record_score_completed(latency_seconds=0.01, rows=1, pack=pack, executor_tag="noop")
    assert snapshot_engine_metrics()["evaluations_total"] == 0


def test_classify_records_translation_when_predicate_not_sql_translatable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compile-time ``can_translate`` false counts as a translation failure when metrics on."""

    monkeypatch.setenv("SPARKRULES_ENGINE_METRICS", "1")
    set_engine_metrics_enabled(None)
    reset_engine_metrics()
    with patch(
        "sparkrules.compiler.translator.translate_predicate",
        side_effect=TranslationError("simulated", node_type="Expr"),
    ):
        r = parse("rule r when $t : T ( true ) then end")
        strat, why = classify_rule_with_rationale(r)
    assert strat == Strategy.ALPHA_SHARED
    assert why == "PREDICATE_NOT_SQL_TRANSLATABLE"
    assert snapshot_engine_metrics()["translation_failures_total"] == 1


def test_classify_records_translation_failure_when_action_does_not_translate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ACTION_NOT_SQL_TRANSLATABLE`` should bump ``translation_failures_total`` when metrics on."""

    monkeypatch.setenv("SPARKRULES_ENGINE_METRICS", "1")
    set_engine_metrics_enabled(None)
    reset_engine_metrics()
    with patch(
        "sparkrules.compiler.rulepack.translate_action",
        side_effect=TranslationError("simulated", node_type="Action"),
    ):
        r = parse("rule r when $t : T ( $t.x > 1 ) then result.flag = true; end")
        strat, _ = classify_rule_with_rationale(r)
    assert strat == Strategy.ALPHA_SHARED
    assert snapshot_engine_metrics()["translation_failures_total"] == 1


def test_translation_failure_records_when_enabled_and_noop_when_disabled() -> None:
    set_engine_metrics_enabled(False)
    reset_engine_metrics()
    record_translation_failure()
    assert snapshot_engine_metrics()["translation_failures_total"] == 0

    set_engine_metrics_enabled(True)
    reset_engine_metrics()
    record_translation_failure()
    record_translation_failure()
    assert snapshot_engine_metrics()["translation_failures_total"] == 2


def test_latency_histogram_all_buckets() -> None:
    """Exercise every ms bucket in `_bucket_latency_ms`."""

    set_engine_metrics_enabled(True)
    pack = RulePack.from_drl("rule r when $t : T ( true ) then end")
    for lat_s, expect_idx in [
        (5e-5, 0),
        (0.0005, 1),
        (0.003, 2),
        (0.01, 3),
        (0.02, 4),
        (0.08, 5),
    ]:
        reset_engine_metrics()
        record_score_completed(
            latency_seconds=lat_s,
            rows=1,
            pack=pack,
            executor_tag=f"b{expect_idx}",
        )
        assert snapshot_engine_metrics()["latency_ms_histogram"][expect_idx] == 1


def test_latency_histogram_buckets_populated() -> None:
    set_engine_metrics_enabled(True)
    reset_engine_metrics()
    pack = RulePack.from_drl("rule r when $t : T ( true ) then end")
    reset_engine_metrics()
    record_score_completed(latency_seconds=0.0001, rows=1, pack=pack, executor_tag="a")
    record_score_completed(
        latency_seconds=0.08, rows=2, pack=pack, executor_tag="b", fires_by_strategy={}
    )
    snap = snapshot_engine_metrics()
    assert sum(snap["latency_ms_histogram"]) == 2
    assert snap["latency_ms_histogram"][0] >= 1
    assert snap["latency_ms_histogram"][-1] >= 1


def test_rollout_config_handles_invalid_max_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_MAX_RULEPACK_BYTES", "not-int")
    c = rollout_config_from_environ()
    assert c.max_rulepack_bytes is None


def test_rollout_config_from_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPARKRULES_SHADOW_DUAL_EVAL", raising=False)
    monkeypatch.delenv("SPARKRULES_ENGINE_METRICS", raising=False)
    monkeypatch.delenv("SPARKRULES_MAX_RULEPACK_BYTES", raising=False)
    c = rollout_config_from_environ()
    assert isinstance(c, RolloutConfig)
    assert c.shadow_dual_eval is False
    assert c.engine_metrics_enabled is False

    monkeypatch.setenv("SPARKRULES_SHADOW_DUAL_EVAL", "1")
    monkeypatch.setenv("SPARKRULES_ENGINE_METRICS", "true")
    monkeypatch.setenv("SPARKRULES_MAX_RULEPACK_BYTES", "4096")
    c2 = rollout_config_from_environ()
    assert c2.shadow_dual_eval and c2.engine_metrics_enabled and c2.max_rulepack_bytes == 4096


def test_compare_v1_v2_single_rule() -> None:
    drl = "rule chk when $t : T ( $t.v == 3 ) then end"
    v1, v2, ok = compare_v1_v2_single_rule_fired({"t": {"v": 3}}, drl)
    assert v1 and v2 and ok


def test_compare_v1_v2_multi_rule_rejects() -> None:
    drl = """
rule a when $t : T ( true ) then end
rule b when $t : T ( true ) then end
"""
    with pytest.raises(ValueError, match="exactly one rule"):
        compare_v1_v2_single_rule_fired({"t": {}}, drl)


def test_classify_rule_with_rationale_codes() -> None:
    from sparkrules.parser import parse

    r0 = parse("rule r when $t : T ( $t.x > 1 ) then end")
    s, code = classify_rule_with_rationale(r0)
    assert s == Strategy.SQL_PUSHDOWN and code == "SQL_PUSH_TRANSLATABLE"


def test_local_executor_logs_fired_at_info(caplog: pytest.LogCaptureFixture) -> None:
    set_engine_metrics_enabled(True)
    ex = LocalRuleExecutor.from_drl("rule z when $t : T ( true ) then end")
    caplog.clear()
    with caplog.at_level(logging.INFO):
        ex.score({"t": {}})
    assert any("rule_fired" in r.message for r in caplog.records)

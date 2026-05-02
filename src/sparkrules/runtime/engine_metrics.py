"""Optional in-process counters and latency buckets for rule evaluation (Req 31).

Enable with environment variable ``SPARKRULES_ENGINE_METRICS=1`` (or ``true``/``yes``),
or force on/off from tests via ``set_engine_metrics_enabled(...)``.

This module intentionally avoids external metric backends; exporters can poll
:func:`snapshot_engine_metrics`.
"""

from __future__ import annotations

import os
import threading
from collections import Counter
from typing import Any

_LOCK = threading.Lock()
_FORCED: bool | None = None

# Cumulative state (process lifetime unless reset).
_state: dict[str, Any] = {
    "evaluations_total": 0,
    "rows_evaluated_total": 0,
    "rules_fired_total": 0,
    "translation_failures_total": 0,
    "classification_rule_hits": Counter(),  # Strategy.name -> count (pack-time)
    "rules_fired_by_strategy": Counter(),  # Strategy.name -> fires at score-time
    "executor_tags": Counter(),
    "latency_ms_histogram": [0, 0, 0, 0, 0, 0],  # <0.25, <1, <5, <15, <50, >=50
}


def engine_metrics_enabled() -> bool:
    if _FORCED is not None:
        return _FORCED
    return os.getenv("SPARKRULES_ENGINE_METRICS", "").lower() in ("1", "true", "yes")


def set_engine_metrics_enabled(value: bool | None) -> None:
    """Force enable/disable (``None`` = follow environment). Intended for tests."""

    global _FORCED
    _FORCED = value


def reset_engine_metrics() -> None:
    """Clear all counters (for tests)."""

    with _LOCK:
        _state["evaluations_total"] = 0
        _state["rows_evaluated_total"] = 0
        _state["rules_fired_total"] = 0
        _state["translation_failures_total"] = 0
        _state["classification_rule_hits"] = Counter()
        _state["rules_fired_by_strategy"] = Counter()
        _state["executor_tags"] = Counter()
        _state["latency_ms_histogram"] = [0, 0, 0, 0, 0, 0]


def _bucket_latency_ms(ms: float) -> None:
    h: list[int] = _state["latency_ms_histogram"]
    if ms < 0.25:
        h[0] += 1
    elif ms < 1:
        h[1] += 1
    elif ms < 5:
        h[2] += 1
    elif ms < 15:
        h[3] += 1
    elif ms < 50:
        h[4] += 1
    else:
        h[5] += 1


def record_translation_failure() -> None:
    if not engine_metrics_enabled():
        return
    with _LOCK:
        _state["translation_failures_total"] += 1


def record_rulepack_classified(pack: Any) -> None:
    """Record static strategy counts once per ``RulePack.from_drl`` (compile-time)."""

    if not engine_metrics_enabled():
        return
    with _LOCK:
        c: Counter[str] = _state["classification_rule_hits"]
        for rule in pack.rules:
            c[rule.strategy.name] += 1


def record_score_completed(
    *,
    latency_seconds: float,
    rows: int,
    pack: Any,
    executor_tag: str,
    fired_rule_names_one_row: list[str] | None = None,
    fires_by_strategy: dict[str, int] | None = None,
) -> None:
    """Record one evaluation batch (e.g. ``LocalRuleExecutor.score`` or ``apply_pandas``).

    For single-fact paths pass ``fired_rule_names_one_row``. For dataframe batches pass
    ``fires_by_strategy`` with total row-level firings keyed by ``Strategy.name``.
    """

    if not engine_metrics_enabled():
        return
    name_to_strat = {r.name: r.strategy.name for r in pack.rules}
    ms = latency_seconds * 1000.0
    with _LOCK:
        _state["evaluations_total"] += 1
        _state["rows_evaluated_total"] += rows
        _state["executor_tags"][executor_tag] += 1
        _bucket_latency_ms(ms)
        fs: Counter[str] = _state["rules_fired_by_strategy"]
        if fires_by_strategy is not None:
            for strat, n in fires_by_strategy.items():
                fs[strat] += n
                _state["rules_fired_total"] += n
        else:
            names = fired_rule_names_one_row or []
            _state["rules_fired_total"] += len(names)
            for nm in names:
                fs[name_to_strat.get(nm, "UNKNOWN")] += 1


def snapshot_engine_metrics() -> dict[str, Any]:
    """Thread-safe copy suitable for logs, tests, or Prometheus bridges."""

    with _LOCK:
        return {
            "evaluations_total": _state["evaluations_total"],
            "rows_evaluated_total": _state["rows_evaluated_total"],
            "rules_fired_total": _state["rules_fired_total"],
            "translation_failures_total": _state["translation_failures_total"],
            "classification_rule_hits": dict(_state["classification_rule_hits"]),
            "rules_fired_by_strategy": dict(_state["rules_fired_by_strategy"]),
            "executor_tags": dict(_state["executor_tags"]),
            "latency_ms_histogram": list(_state["latency_ms_histogram"]),
            "latency_ms_histogram_labels": ["<0.25", "<1", "<5", "<15", "<50", ">=50"],
        }


def max_rulepack_bytes_from_environ() -> int | None:
    raw = os.getenv("SPARKRULES_MAX_RULEPACK_BYTES")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


__all__ = [
    "engine_metrics_enabled",
    "max_rulepack_bytes_from_environ",
    "record_rulepack_classified",
    "record_score_completed",
    "record_translation_failure",
    "reset_engine_metrics",
    "set_engine_metrics_enabled",
    "snapshot_engine_metrics",
]

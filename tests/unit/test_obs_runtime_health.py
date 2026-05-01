from __future__ import annotations

from sparkrules.obs import (
    StageMetric,
    detect_runtime_issues,
    observability_ui_payload,
    summarize_runtime_health,
)


def test_detect_runtime_issues_for_slow_shuffle_and_failures() -> None:
    stages = [
        StageMetric(
            stage_id=1,
            duration_ms=130000,
            shuffle_read_mb=800,
            shuffle_write_mb=400,
            failed_tasks=2,
        ),
        StageMetric(
            stage_id=2, duration_ms=1000, shuffle_read_mb=1, shuffle_write_mb=1, failed_tasks=0
        ),
    ]
    issues = detect_runtime_issues(stages)
    assert "stage_1:slow_stage" in issues
    assert "stage_1:high_shuffle" in issues
    assert "stage_1:task_failures" in issues


def test_runtime_health_summary_and_ui_payload() -> None:
    stages = [
        StageMetric(
            stage_id=1, duration_ms=10, shuffle_read_mb=1, shuffle_write_mb=2, failed_tasks=0
        )
    ]
    s = summarize_runtime_health(stages)
    assert s["status"] == "ok"
    assert s["stage_count"] == 1
    p = observability_ui_payload("run-1", stages)
    assert p["run_id"] == "run-1"
    assert len(p["stages"]) == 1


def test_runtime_health_empty_and_warning_states() -> None:
    empty = summarize_runtime_health([])
    assert empty["avg_stage_ms"] == 0
    bad = summarize_runtime_health(
        [
            StageMetric(
                stage_id=9,
                duration_ms=200000,
                shuffle_read_mb=2000,
                shuffle_write_mb=0,
                failed_tasks=0,
            )
        ]
    )
    assert bad["status"] == "warning"

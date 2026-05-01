from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True, slots=True)
class StageMetric:
    stage_id: int
    duration_ms: int
    shuffle_read_mb: int
    shuffle_write_mb: int
    failed_tasks: int = 0


def detect_runtime_issues(
    stages: list[StageMetric],
    *,
    slow_stage_ms: int = 120_000,
    shuffle_warn_mb: int = 1_024,
) -> list[str]:
    out: list[str] = []
    for s in stages:
        if s.duration_ms >= slow_stage_ms:
            out.append(f"stage_{s.stage_id}:slow_stage")
        if s.shuffle_read_mb + s.shuffle_write_mb >= shuffle_warn_mb:
            out.append(f"stage_{s.stage_id}:high_shuffle")
        if s.failed_tasks > 0:
            out.append(f"stage_{s.stage_id}:task_failures")
    return out


def summarize_runtime_health(stages: list[StageMetric]) -> dict[str, object]:
    issues = detect_runtime_issues(stages)
    avg_ms = int(mean([s.duration_ms for s in stages])) if stages else 0
    total_shuffle = sum(s.shuffle_read_mb + s.shuffle_write_mb for s in stages)
    status = "ok" if not issues else "warning"
    return {
        "status": status,
        "stage_count": len(stages),
        "avg_stage_ms": avg_ms,
        "total_shuffle_mb": total_shuffle,
        "issues": issues,
    }


def observability_ui_payload(run_id: str, stages: list[StageMetric]) -> dict[str, object]:
    summary = summarize_runtime_health(stages)
    return {
        "run_id": run_id,
        "summary": summary,
        "stages": [
            {
                "stage_id": s.stage_id,
                "duration_ms": s.duration_ms,
                "shuffle_read_mb": s.shuffle_read_mb,
                "shuffle_write_mb": s.shuffle_write_mb,
                "failed_tasks": s.failed_tasks,
            }
            for s in stages
        ],
    }

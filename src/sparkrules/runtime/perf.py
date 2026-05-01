from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter


@dataclass(frozen=True, slots=True)
class PerfRun:
    rows: int
    elapsed_ms: float
    rows_per_sec: float


def run_perf_harness(rows: int, fn) -> PerfRun:
    t0 = perf_counter()
    fn()
    elapsed_ms = (perf_counter() - t0) * 1000.0
    rps = rows / max(elapsed_ms / 1000.0, 1e-9)
    return PerfRun(rows=rows, elapsed_ms=elapsed_ms, rows_per_sec=rps)


def estimate_scale_runtime(rows: int, rows_per_sec: float) -> timedelta:
    seconds = rows / max(rows_per_sec, 1e-9)
    return timedelta(seconds=seconds)


def scale_evidence(rows: int, rows_per_sec: float, *, target_rows: int = 1_000_000_000) -> dict[str, str]:
    eta = estimate_scale_runtime(target_rows, rows_per_sec)
    return {
        "observed_rows": str(rows),
        "rows_per_sec": f"{rows_per_sec:.3f}",
        "target_rows": str(target_rows),
        "estimated_runtime": str(eta),
        "generated_at": datetime.now(UTC).isoformat(),
    }

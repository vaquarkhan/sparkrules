"""Controlled failure injection and a tiny throughput harness.

- :func:`sparkrules.runtime.chaos.run_chaos_scenario`
- :func:`sparkrules.runtime.perf.run_perf_harness` + :func:`sparkrules.runtime.perf.scale_evidence`

  python examples/python/chaos_and_perf_harness_demo.py
"""

from __future__ import annotations

from sparkrules.runtime.chaos import ChaosPolicy, run_chaos_scenario
from sparkrules.runtime.perf import run_perf_harness, scale_evidence


def main() -> None:
    def flaky() -> int:
        return 42

    res = run_chaos_scenario(
        flaky,
        ChaosPolicy(fail_on_attempts=(1,), max_retries=2),
    )
    print("chaos:", res.ok, "attempts=", res.attempts, "events=", res.events)

    pr = run_perf_harness(10_000, lambda: sum(range(1000)))
    ev = scale_evidence(pr.rows, pr.rows_per_sec, target_rows=50_000_000)
    print("perf rows/s=", round(pr.rows_per_sec, 1), "scale hint:", ev)


if __name__ == "__main__":
    main()

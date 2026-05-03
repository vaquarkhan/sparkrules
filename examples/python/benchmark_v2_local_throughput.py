"""Rough throughput check for ``LocalRuleExecutor`` (same spirit as ``docs/BENCHMARKS.md``).

Not a substitute for full CI benchmarks — use to sanity-check your machine::

    python examples/python/benchmark_v2_local_throughput.py

"""

from __future__ import annotations

import time

from sparkrules.executor.local_executor import LocalRuleExecutor

DRL = """
rule "r" when $t : T ( $t.x > 5 and $t.y < 20 ) then result.ok = true; end
"""


def main() -> int:
    ex = LocalRuleExecutor.from_drl(DRL)
    fact = {"t": {"x": 10, "y": 10}}
    n = 50_000
    t0 = time.perf_counter()
    for _ in range(n):
        ex.score(fact)
    sec = time.perf_counter() - t0
    print(f"{n} scores in {sec:.3f}s  (~{n / sec:,.0f} evals/sec)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

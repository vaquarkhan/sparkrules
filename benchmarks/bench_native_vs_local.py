"""Tier-1 throughput: LocalRuleExecutor vs NativeRuleExecutor (30-rule taxi pack).

Writes ``benchmarks/native_tier1_results.json``. Skips native path if wheel missing.
Requires ``pytest`` extras only for timers; runs as ``python benchmarks/bench_native_vs_local.py``.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent


def synthetic_facts(count: int) -> list[dict]:
    rnd = random.Random(42)
    out: list[dict] = []
    for _ in range(count):
        out.append(
            {
                "t": {
                    "fare": rnd.uniform(0, 120),
                    "distance": rnd.uniform(0, 30),
                    "pax": rnd.randint(0, 5),
                    "tip_pct": rnd.uniform(0, 40),
                    "city": rnd.choice(["NYC", "LA", "CHI"]),
                    "code": rnd.choice(["L1", "L9", "X"]),
                    "bad_driver": rnd.choice([True, False, None]),
                    "surged": rnd.choice([True, False]),
                    "delta": rnd.uniform(-30, 30),
                    "notes": rnd.choice(["", "abcd", "x" * 6]),
                    "fare_int": rnd.randint(0, 100),
                    "vip": rnd.choice([True, False]),
                    "pickup_hour": rnd.randint(0, 23),
                    "dropoff_hour": rnd.randint(0, 23),
                    "echo_fare": rnd.uniform(0, 120),
                    "rating": rnd.uniform(1, 5),
                },
            },
        )
    return out


def bench_local(rows: list[dict], drl: str) -> tuple[float, int]:
    from sparkrules.executor.local_executor import LocalRuleExecutor

    ex = LocalRuleExecutor.from_drl(drl)
    n = len(rows)
    t0 = time.perf_counter()
    for r in rows:
        ex.score(r)
    secs = max(time.perf_counter() - t0, 1e-9)
    return secs, n


def bench_native(rows: list[dict], drl: str) -> tuple[float, int | None]:
    try:
        from sparkrules.native.bridge import load_native

        if load_native() is None:
            return 0.0, None
        from sparkrules.native.executor import NativeRuleExecutor
    except Exception:
        return 0.0, None

    ex = NativeRuleExecutor.from_drl(drl)
    n = len(rows)
    t0 = time.perf_counter()
    for r in rows:
        ex.score(r)
    secs = max(time.perf_counter() - t0, 1e-9)
    return secs, n


def main() -> None:
    workload_rel = "deploy/aws-glue/glue_job/taxi_rules_30.drl"
    taxi = (_REPO / workload_rel).read_text(encoding="utf-8")
    count = min(
        100_000, int(__import__("os").environ.get("SPARKRULES_NATIVE_BENCH_ROWS", "100000"))
    )
    rows = synthetic_facts(count)
    secs_l, n = bench_local(rows, taxi)

    secs_n, nn = bench_native(rows, taxi)

    rows_per_sec_local = round(n / secs_l)
    tier1_native = {}
    ratio = None
    if nn is not None:
        rows_per_sec_native = round(n / secs_n) if secs_n > 0 else 0
        ratio = rows_per_sec_native / max(rows_per_sec_local, 1)
        tier1_native = {
            "rows": n,
            "seconds": round(secs_n, 6),
            "rows_per_sec": rows_per_sec_native,
            "speedup_vs_local": round(ratio, 2),
        }

    blob = {
        "tier": 1,
        "workload": workload_rel.replace("\\", "/"),
        "bench_rows_requested": count,
        "local": {"rows": n, "seconds": round(secs_l, 6), "rows_per_sec": rows_per_sec_local},
        "native": tier1_native if tier1_native else None,
        "note": (
            "Native row null when sparkrules_native is not installed. "
            "Target: ≥40x vs LocalTier-1 for this benchmark on a warmed release build."
        ),
    }

    outp = Path(__file__).with_name("native_tier1_results.json")
    outp.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    print(json.dumps(blob, indent=2))


if __name__ == "__main__":
    main()

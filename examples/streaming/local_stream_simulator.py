"""Offline stream simulator: synthetic or JSONL facts → LocalRuleExecutor (no Kafka / JVM).

Use this to validate DRL and latency before wiring Spark or Flink.

  # 20 random amounts (seeded)
  python local_stream_simulator.py --count 20

  # Facts from a file (one JSON object per line, keys inside {"t": {...}} or flat for "amount")
  python local_stream_simulator.py --jsonl sample_events.jsonl

Requires: pip install sparkrules (core engine only)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

_RULES = Path(__file__).resolve().parent / "rules" / "ingress.drl"


def _load_drl(path: str | None) -> str:
    if path and Path(path).is_file():
        return Path(path).read_text(encoding="utf-8")
    env = (os.environ.get("SPARKRULES_DRL_PATH", "") or "").strip()
    for candidate in (Path(env) if env else _RULES, _RULES):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(f"DRL not found; set --drl or SPARKRULES_DRL_PATH (tried {_RULES}).")


def _parse_line(line: str) -> dict[str, object]:
    raw = json.loads(line)
    if isinstance(raw, dict) and "t" in raw:
        return raw  # type: ignore[return-value]
    if isinstance(raw, dict) and "amount" in raw:
        return {"t": raw}
    raise ValueError(
        'Expected a dict with key "t" or flat "amount"; got keys: ' + str(list(raw.keys()))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate a rule stream with LocalRuleExecutor.")
    parser.add_argument(
        "--count", type=int, default=10, help="Synthetic events (ignored if --jsonl)."
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for synthetic amounts.")
    parser.add_argument(
        "--jsonl", type=str, default="", help="Path to newline-delimited JSON facts."
    )
    parser.add_argument("--drl", type=str, default="", help="Override DRL file path.")
    args = parser.parse_args()

    drl = _load_drl(args.drl or None)
    from sparkrules.executor.local_executor import LocalRuleExecutor

    exe = LocalRuleExecutor.from_drl(drl)

    if args.jsonl and Path(args.jsonl).is_file():
        lines = Path(args.jsonl).read_text(encoding="utf-8").strip().splitlines()
    else:
        rnd = random.Random(args.seed)
        lines = [
            json.dumps(
                {"t": {"amount": rnd.randint(0, 25000)}},
            )
            for _ in range(max(1, args.count))
        ]

    n_fired = 0
    for i, line in enumerate(lines):
        fact = _parse_line(line)
        r = exe.score(fact)
        if r.fired_any:
            n_fired += 1
        out = {
            "seq": i,
            "fired": r.fired_any,
            "actions": r.merged_actions,
        }
        print(json.dumps(out))

    print(
        json.dumps({"summary": True, "events": len(lines), "batches_with_fire": n_fired}),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

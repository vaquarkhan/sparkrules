from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from sparkrules.compiler.classifier import Strategy


@dataclass(frozen=True, slots=True)
class RuleBatch:
    batch_id: int
    rule_ids: tuple[str, ...]
    strategy: str


@dataclass
class RuleBatcher:
    batch_size: int = 200

    def batch(
        self,
        rule_ids: list[str],
        strategy_by_rule_id: Mapping[str, Strategy] | None = None,
    ) -> list[RuleBatch]:
        if not strategy_by_rule_id:
            out: list[RuleBatch] = []
            b = 0
            for start in range(0, len(rule_ids), self.batch_size):
                chunk = tuple(rule_ids[start : start + self.batch_size])
                out.append(RuleBatch(b, chunk, "BROADCAST"))
                b += 1
            return out

        stmap = strategy_by_rule_id
        out2: list[RuleBatch] = []
        bid = 0
        bucket: list[str] = []
        bucket_strategy = ""

        def flush() -> None:
            nonlocal bid, bucket, bucket_strategy
            if not bucket:
                return
            chunk = tuple(bucket)
            strat_name = bucket_strategy
            bucket = []
            for start in range(0, len(chunk), self.batch_size):
                out2.append(RuleBatch(bid, chunk[start : start + self.batch_size], strat_name))
                bid += 1

        for rid in rule_ids:
            sn = stmap.get(rid, Strategy.BROADCAST).name
            if bucket and sn != bucket_strategy:
                flush()
            if not bucket:
                bucket_strategy = sn
            bucket.append(rid)
        flush()
        return out2

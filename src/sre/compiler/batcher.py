from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RuleBatch:
    batch_id: int
    rule_ids: tuple[str, ...]
    strategy: str


@dataclass
class RuleBatcher:
    batch_size: int = 200

    def batch(self, rule_ids: list[str]) -> list[RuleBatch]:  # type: ignore[no-untyped-def]  # noqa: E501
        out: list[RuleBatch] = []
        b = 0
        for start in range(0, len(rule_ids), self.batch_size):
            chunk = tuple(rule_ids[start : start + self.batch_size])
            out.append(RuleBatch(b, chunk, "BROADCAST"))
            b += 1
        return out

from __future__ import annotations

import pickle
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class BroadcastChunk:
    index: int
    payload: bytes
    count: int


@dataclass
class Broadcast(Generic[T]):
    data: T
    eager: bool = True


@dataclass
class RuleBroadcaster:
    size_threshold: int = 1_000_000

    def chunk(self, package_bytes: bytes) -> list[BroadcastChunk]:
        if len(package_bytes) <= self.size_threshold:
            return [BroadcastChunk(0, package_bytes, 1)]
        out: list[BroadcastChunk] = []
        for i, start in enumerate(range(0, len(package_bytes), self.size_threshold)):
            b = package_bytes[start : start + self.size_threshold]
            out.append(BroadcastChunk(i, b, i + 1))
        return out

    def round_trip(self, data: object) -> object:
        b = pickle.dumps(data, protocol=4)
        ch = self.chunk(b)
        merged = b"".join(c.payload for c in ch)
        return pickle.loads(merged)


def rule_broadcast(obj: object) -> bytes:
    return pickle.dumps(obj, protocol=4)

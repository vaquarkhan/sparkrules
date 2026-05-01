from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Variant:
    name: str
    weight: int


@dataclass
class ABTestConfig:
    key_field: str
    variants: tuple[Variant, ...] = (Variant("A", 1), Variant("B", 1))


@dataclass
class ABTestRunner:
    def assign(self, key: str, cfg: ABTestConfig) -> str:
        h = int.from_bytes(
            hashlib.sha256((key + cfg.key_field).encode()).digest()[:4],
            "big",
        )
        tot = max(1, sum(v.weight for v in cfg.variants))
        t = h % tot
        acc = 0
        for v in cfg.variants:
            acc += v.weight
            if t < acc:
                return v.name
        return cfg.variants[-1].name

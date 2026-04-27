from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

STANDARD_ENVS: tuple[str, ...] = ("dev", "stage", "prod")

ADJACENT_PROMOTIONS: frozenset[tuple[str, str]] = frozenset(
    {("dev", "stage"), ("stage", "prod")}
)


@dataclass
class PromotionRegistry:
    """(namespace, rule_handle, environment) -> pinned version for dev/stage/prod."""

    _pins: dict[tuple[str, str, str], int] = field(default_factory=dict)

    def get_pin(
        self, namespace: str, handle: str, environment: str
    ) -> int | None:
        return self._pins.get((namespace, handle, environment))

    def set_pin(
        self, namespace: str, handle: str, environment: str, version: int
    ) -> None:
        if environment not in STANDARD_ENVS:
            raise ValueError(f"unknown environment: {environment!r}")
        self._pins[(namespace, handle, environment)] = version

    def promote(
        self, namespace: str, handle: str, from_env: str, to_env: str
    ) -> int:
        if (from_env, to_env) not in ADJACENT_PROMOTIONS:
            raise ValueError(
                "only adjacent promotion is supported (dev→stage, stage→prod)"
            )
        v = self.get_pin(namespace, handle, from_env)
        if v is None:
            raise ValueError("source environment has no pin; sync dev first")
        self.set_pin(namespace, handle, to_env, v)
        return v

    def all_pins(
        self, namespace: str | None = None
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for (ns, h, e), v in sorted(self._pins.items()):
            if namespace and ns != namespace:
                continue
            rows.append(
                {
                    "namespace": ns,
                    "rule_handle": h,
                    "environment": e,
                    "version": v,
                }
            )
        return rows

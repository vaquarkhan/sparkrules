from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class UnknownUdfError(KeyError):
    pass


@dataclass(frozen=True, slots=True)
class UdfDefinition:
    function_name: str
    version: int
    input_signature: tuple[str, ...]
    return_type: str
    pure: bool
    body: str
    active: bool = True
    activated_at: datetime | None = None


@dataclass
class UserDefinedFunctionRegistry:
    _by_name: dict[str, list[UdfDefinition]] = field(default_factory=dict)

    def register(self, u: UdfDefinition) -> UdfDefinition:
        arr = self._by_name.setdefault(u.function_name, [])
        arr.append(u)
        arr.sort(key=lambda x: x.version)
        return u

    def resolve_latest_active(self, name: str) -> UdfDefinition:
        arr = [x for x in self._by_name.get(name, []) if x.active]
        if not arr:
            raise UnknownUdfError(name)
        return max(arr, key=lambda x: x.version)

    def resolve_at_time(self, name: str, t: datetime) -> UdfDefinition:
        arr = [
            x for x in self._by_name.get(name, [])
            if x.active and (x.activated_at is None or x.activated_at <= t)
        ]
        if not arr:
            raise UnknownUdfError(name)
        return max(arr, key=lambda x: x.version)


def eval_registered_pure_udf(defn: UdfDefinition, args: tuple[Any, ...]) -> Any:
    if not defn.pure:
        raise ValueError("impure udf requires sandbox")
    if defn.body == "sum":
        return sum(args)
    if defn.body == "len":
        return len(args[0]) if args else 0
    raise ValueError("unsupported udf body")

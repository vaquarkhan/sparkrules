from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from sparkrules.compiler import CompiledRulePackage


@dataclass
class StatefulContext:
    state: dict[str, Any] = field(default_factory=dict)
    last_ts: datetime | None = None


@dataclass
class MicroBatchResult:
    run_id: str
    count: int
    version: str


@dataclass
class StreamingRuleRefresher:
    current: str = ""

    def maybe_refresh(
        self, new_version: str, *, recompile: Callable[[], "CompiledRulePackage"] | None
    ) -> str | None:
        if new_version == self.current:
            return None
        if recompile is not None:
            try:
                recompile()
            except Exception:
                return None
        self.current = new_version
        return new_version


@dataclass
class StreamingEvaluator:
    ttl: timedelta = field(default=timedelta(seconds=30))

    def check_ttl(self, t: datetime, last: datetime | None) -> bool:
        if last is None:
            return True
        return t - last > self.ttl


def default_executor_factory() -> str:
    return "in_process"

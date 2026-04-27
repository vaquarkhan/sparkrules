from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class StreamNotification:
    run_id: str
    fact_id: str
    decision: str
    reason_codes: tuple[str, ...]
    rule_set_version: str
    emitted_ts: str


@dataclass
class InMemoryStreamSink:
    fail: bool = False
    emitted: list[StreamNotification] = field(default_factory=list)

    def emit(self, item: StreamNotification) -> None:
        if self.fail:
            raise RuntimeError("stream sink unavailable")
        self.emitted.append(item)


@dataclass
class StreamEmitter:
    sink: InMemoryStreamSink
    missed: list[StreamNotification] = field(default_factory=list)

    def dual_write(
        self,
        item: StreamNotification,
        *,
        persist_fn: callable,
    ) -> bool:
        persist_fn(item)
        try:
            self.sink.emit(item)
            return True
        except Exception:  # noqa: BLE001
            self.missed.append(item)
            return False

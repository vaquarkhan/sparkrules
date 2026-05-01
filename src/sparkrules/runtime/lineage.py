from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class LineageEvent:
    event_type: str
    run_id: str
    ts: str
    payload: dict[str, Any]


class LineageSink(Protocol):
    def emit(self, event: LineageEvent) -> None: ...


@dataclass
class InMemoryLineageSink:
    events: list[LineageEvent] = field(default_factory=list)

    def emit(self, event: LineageEvent) -> None:
        self.events.append(event)


def make_lineage_event(
    event_type: str,
    run_id: str,
    *,
    payload: dict[str, Any],
) -> LineageEvent:
    return LineageEvent(
        event_type=event_type,
        run_id=run_id,
        ts=datetime.now(UTC).isoformat(),
        payload=payload,
    )

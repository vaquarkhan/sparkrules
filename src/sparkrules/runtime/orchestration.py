from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sparkrules.runtime.streaming import StreamingRuleRefresher


@dataclass
class StreamingOrchestrator:
    refresher: StreamingRuleRefresher
    current_version: str = ""
    refresh_history: list[str] = field(default_factory=list)

    def on_micro_batch(self, *, requested_version: str, recompile=None) -> str:
        updated = self.refresher.maybe_refresh(requested_version, recompile=recompile)
        if updated is not None:
            self.current_version = updated
            self.refresh_history.append(updated)
        return self.current_version or requested_version


def make_event(run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "event_time": datetime.now(UTC).isoformat(),
        "payload": payload,
    }

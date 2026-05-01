from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class DeprecationRecord:
    namespace: str
    rule_handle: str
    requested_by: str
    reason: str
    status: str
    requested_at: str
    approved_by: str | None = None
    approved_at: str | None = None


@dataclass
class DeprecationRegistry:
    _records: dict[tuple[str, str], DeprecationRecord] = field(default_factory=dict)

    def propose(
        self,
        *,
        namespace: str,
        rule_handle: str,
        requested_by: str,
        reason: str,
    ) -> DeprecationRecord:
        now = datetime.now(UTC).isoformat()
        r = DeprecationRecord(
            namespace=namespace,
            rule_handle=rule_handle,
            requested_by=requested_by,
            reason=reason,
            status="PROPOSED",
            requested_at=now,
        )
        self._records[(namespace, rule_handle)] = r
        return r

    def approve(
        self,
        *,
        namespace: str,
        rule_handle: str,
        approved_by: str,
    ) -> DeprecationRecord:
        key = (namespace, rule_handle)
        r = self._records.get(key)
        if r is None:
            raise KeyError(key)
        now = datetime.now(UTC).isoformat()
        out = DeprecationRecord(
            namespace=r.namespace,
            rule_handle=r.rule_handle,
            requested_by=r.requested_by,
            reason=r.reason,
            status="APPROVED",
            requested_at=r.requested_at,
            approved_by=approved_by,
            approved_at=now,
        )
        self._records[key] = out
        return out

    def list(self, namespace: str | None = None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for (_, _), r in sorted(self._records.items()):
            if namespace and r.namespace != namespace:
                continue
            out.append(
                {
                    "namespace": r.namespace,
                    "rule_handle": r.rule_handle,
                    "requested_by": r.requested_by,
                    "reason": r.reason,
                    "status": r.status,
                    "requested_at": r.requested_at,
                    "approved_by": r.approved_by,
                    "approved_at": r.approved_at,
                }
            )
        return out

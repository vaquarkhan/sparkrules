from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypeAlias
from uuid import UUID

from sparkrules.model.rule import Rule, new_rule_id, now_utc


@dataclass(frozen=True, slots=True)
class RuleFilter:
    rule_handle: str | None = None
    rule_group: str | None = None
    namespace: str | None = None
    is_active: bool | None = None
    at_time: datetime | None = None


class ConflictError(ValueError):
    pass


class UnknownRuleError(KeyError):
    pass


def _overlaps(
    a0: datetime, a1: datetime | None, b0: datetime, b1: datetime | None
) -> bool:
    """Return True if half-open [a0, a1) and [b0, b1) overlap (a1 or b1 None = +inf)."""
    if a1 is not None and a1 <= b0:
        return False
    if b1 is not None and b1 <= a0:
        return False
    return True


@dataclass
class InMemoryRuleMetadataStore:
    _by_handle: dict[str, list[Rule]] = field(default_factory=dict)
    _by_id: dict[UUID, Rule] = field(default_factory=dict)

    def _next_version(self, handle: str) -> int:
        v = self._by_handle.get(handle) or []
        return max((r.version for r in v), default=0) + 1

    def _check_overlap(
        self,
        handle: str,
        eff_from: datetime,
        eff_to: datetime | None,
        is_active: bool,
        ignore_version: int | None = None,
    ) -> None:
        if not is_active:
            return
        for r in self._by_handle.get(handle, ()):
            if r.version == ignore_version:
                continue
            if not r.is_active:
                continue
            if _overlaps(
                r.effective_from, r.effective_to, eff_from, eff_to
            ):
                raise ConflictError(
                    f"overlapping active window for {handle!r} v{r.version} vs new"
                )

    def insert(self, r: Rule) -> Rule:
        h = r.rule_handle
        ver = self._next_version(h)
        self._check_overlap(h, r.effective_from, r.effective_to, r.is_active, None)
        out = r.with_updates(
            rule_id=new_rule_id(), version=ver, created_at=now_utc()
        )
        self._by_handle.setdefault(h, []).append(out)
        self._by_id[out.rule_id] = out
        return out

    def update(self, rule_handle: str, patch: Rule) -> Rule:
        arr = self._by_handle.get(rule_handle)
        if not arr:
            raise UnknownRuleError(rule_handle)
        for i, r in enumerate(arr):
            if r.version == patch.version:
                self._check_overlap(
                    rule_handle,
                    patch.effective_from,
                    patch.effective_to,
                    patch.is_active,
                    ignore_version=patch.version,
                )
                new = r.with_updates(
                    salience=patch.salience,
                    is_active=patch.is_active,
                    effective_from=patch.effective_from,
                    effective_to=patch.effective_to,
                    rule_definition=patch.rule_definition,
                    activation_group=patch.activation_group,
                    reason_codes=patch.reason_codes,
                    pass_=patch.pass_,
                    group_by_keys=patch.group_by_keys,
                    source_file_hash=patch.source_file_hash,
                    author_principal=patch.author_principal,
                    namespace=patch.namespace,
                )
                arr[i] = new
                self._by_id[new.rule_id] = new
                return new
        raise UnknownRuleError(f"{rule_handle}@{patch.version}")

    def soft_delete(self, rule_handle: str) -> list[Rule]:
        res: list[Rule] = []
        for r in self._by_handle.get(rule_handle, ()):
            p = r.with_updates(is_active=False)
            res.append(self.update(rule_handle, p))
        return res

    def activate(self, rule_handle: str, version: int) -> Rule:
        for r in self._by_handle.get(rule_handle, ()):
            if r.version == version:
                p = r.with_updates(is_active=True)
                return self.update(rule_handle, p)
        raise UnknownRuleError(f"{rule_handle}@{version}")

    def get(self, rule_handle: str, version: int) -> Rule:
        for r in self._by_handle.get(rule_handle, ()):
            if r.version == version:
                return r
        raise UnknownRuleError(f"{rule_handle}@{version}")

    def get_by_id(self, rule_id: UUID) -> Rule:
        r = self._by_id.get(rule_id)
        if r is None:
            raise UnknownRuleError(str(rule_id))
        return r

    def resolve(self, rule_handle: str, t: datetime) -> Rule | None:
        cands = [
            r
            for r in self._by_handle.get(rule_handle, ())
            if r.is_active
            and r.effective_from <= t
            and (r.effective_to is None or t <= r.effective_to)
        ]
        if not cands:
            return None
        return max(cands, key=lambda r: r.version)

    def list(self, f: RuleFilter | None) -> list[Rule]:
        res: list[Rule] = []
        for h, arr in self._by_handle.items():
            if f and f.rule_handle and f.rule_handle != h:
                continue
            for r in arr:
                if f and f.rule_group and r.rule_group != f.rule_group:
                    continue
                if f and f.namespace and r.namespace != f.namespace:
                    continue
                if f and f.is_active is not None and r.is_active != f.is_active:
                    continue
                if f and f.at_time is not None:
                    at = f.at_time
                    if not (
                        r.effective_from <= at
                        and (r.effective_to is None or at <= r.effective_to)
                    ):
                        continue
                res.append(r)
        return res

    def list_versions(self, rule_handle: str) -> list[Rule]:
        return list(self._by_handle.get(rule_handle, ()))

    def active_set_version(self, t: datetime) -> str:
        by_h: dict[str, int] = {}
        for h, arr in self._by_handle.items():
            for r in arr:
                if not r.is_active:
                    continue
                if r.effective_from <= t and (
                    r.effective_to is None or t <= r.effective_to
                ):
                    if r.version > by_h.get(h, -1):
                        by_h[h] = r.version
        s = ",".join(f"{h}:{by_h[h]}" for h in sorted(by_h))
        return hashlib.sha256(s.encode()).hexdigest()


RuleMetadataStore: TypeAlias = InMemoryRuleMetadataStore

from __future__ import annotations

import copy
import pickle
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

Row = dict[str, Any]
Pred = Callable[[Row], bool]


class UnknownSnapshotError(KeyError):
    pass


@dataclass
class IcebergLikeTable:
    name: str
    schema: dict[str, type] = field(default_factory=dict)
    append_only: bool = False
    _snapshots: dict[int, list[Row]] = field(
        default_factory=dict, repr=False
    )
    _current: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        if 0 not in self._snapshots:
            self._snapshots[0] = []
            self._current = 0

    def append(self, rows: Sequence[Row]) -> int:
        self._current += 1
        base = self._snapshots.get(self._current - 1, [])
        nxt = list(base) + [copy.deepcopy(r) for r in rows]
        self._snapshots[self._current] = nxt
        return self._current

    def snapshot(self, sid: int) -> list[Row]:
        if sid not in self._snapshots:
            raise UnknownSnapshotError(sid)
        return [copy.deepcopy(r) for r in self._snapshots[sid]]

    def current_snapshot_id(self) -> int:
        return self._current

    def row_count(self, sid: int) -> int:
        return len(self.snapshot(sid))

    def delete_rows(self, predicate: Pred) -> int:
        if self.append_only:
            raise ValueError("append-only table does not allow delete_rows")
        self._current += 1
        prev = self._snapshots.get(self._current - 1, [])
        nxt = [r for r in prev if not predicate(r)]
        self._snapshots[self._current] = nxt
        return self._current

    def __getstate__(self) -> object:
        return (self.name, self.schema, self.append_only, self._snapshots, self._current)

    def __setstate__(self, s: object) -> None:
        if isinstance(s, tuple) and len(s) == 4:
            a, b, c, d = s  # type: ignore[misc]
            self.name, self.schema, self.append_only, self._snapshots, self._current = (
                a,
                b,
                False,
                c,
                d,
            )
            return
        a, b, c, d, e = s  # type: ignore[misc]
        self.name, self.schema, self.append_only, self._snapshots, self._current = a, b, c, d, e

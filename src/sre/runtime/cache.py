from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Hashable, MutableMapping


@dataclass
class DerivedColumnCache:
    _d: dict[tuple[Hashable, str], Any] = field(
        default_factory=dict, init=False, repr=False
    )
    _lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False
    )

    def get(self, key: tuple[Hashable, str]) -> Any:
        with self._lock:
            return self._d.get(key)

    def put(self, key: tuple[Hashable, str], v: Any) -> None:
        with self._lock:
            self._d[key] = v

    def clear(self) -> None:
        with self._lock:
            self._d.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._d)

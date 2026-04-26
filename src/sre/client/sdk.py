from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx


class SreClientError(Exception):
    pass


@dataclass
class SreClient:
    base_url: str
    inproc: object | None = None
    _tries: int = 3
    _fails: int = field(default=0, init=False, repr=False)

    def get(self, p: str) -> httpx.Response:
        e: Exception | None = None
        u = f"{self.base_url.rstrip('/')}{p}"
        for a in range(self._tries):
            if self._fails and a < self._fails:
                e = SreClientError("injected")
                time.sleep(0.0)
                continue
            with httpx.Client() as c:
                return c.get(u, timeout=10.0)
        raise e or SreClientError("unreachable")

    def health(self) -> dict[str, str]:
        r = self.get("/health")
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    @staticmethod
    def install_transient_failure(c: SreClient, n: int) -> None:
        c._fails = n  # type: ignore[attr-defined]


def install_transient_failure(c: SreClient, n: int) -> None:
    SreClient.install_transient_failure(c, n)

from __future__ import annotations

import pytest
from starlette.requests import Request

from sparkrules.api import security as sec


def test_api_key_matches_returns_false_on_compare_digest_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPARKRULES_API_KEY", "same-key")

    def _boom(a: bytes, b: bytes) -> bool:
        raise ValueError()

    monkeypatch.setattr(sec.hmac, "compare_digest", _boom)
    scope: dict[str, object] = {"type": "http", "headers": [[b"x-api-key", b"same-key"]]}
    req = Request(scope)  # type: ignore[arg-type]
    assert sec.api_key_matches_request(req) is False

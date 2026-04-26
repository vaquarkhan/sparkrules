"""Auth / streaming path (ladder: idea-brainstrom §8)."""
from __future__ import annotations

import pytest

from sre.api import create_app, AppDeps
from fastapi.testclient import TestClient
from sre.runtime.streaming import (
    StreamingEvaluator,
    StreamingRuleRefresher,
)
from sre.sim.ab import ABTestConfig, ABTestRunner, Variant

pytestmark = pytest.mark.integration


def test_streaming_refresher_noop_same_version() -> None:
    r = StreamingRuleRefresher("v0")
    assert r.maybe_refresh("v0", recompile=None) is None


def test_streaming_eval_ttl_bracket() -> None:
    s = StreamingEvaluator()
    from datetime import UTC, datetime, timedelta

    t = datetime(2020, 1, 1, tzinfo=UTC)
    assert s.check_ttl(t, t - timedelta(seconds=100)) is True


def test_auth_ab_assignment_stable() -> None:
    c = ABTestConfig("k", (Variant("allow", 1), Variant("deny", 1)))
    a = ABTestRunner()
    assert a.assign("subj", c) == a.assign("subj", c)


def test_api_simulate_authz_rule() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations",
        json={
            "drl": "rule a when $u : T ( 1==1 ) then result.ok=1; end",
            "fact": {"u": 1},
        },
    )
    assert r.status_code == 200



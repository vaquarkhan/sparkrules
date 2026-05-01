"""POS end-of-day style flow (ladder: idea-brainstrom §8)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sparkrules.api import AppDeps, create_app
from sparkrules.runtime.batch import BatchEvaluator
from sparkrules.runtime.two_pass import TwoPassOrchestrator

pytestmark = pytest.mark.integration

P1 = """
rule p1
when
$t : T ( $t.amt > 0 )
then
result.eligible = 1;
end
"""
P2 = """
rule p2
when
$t : T ( 1==1 )
then
result.capped = 1;
end
"""


def test_pos_api_health() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    assert c.get("/health").json()["status"] == "ok"


def test_pos_store_list_after_rule_post() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/rules",
        json={"rule_handle": "pos_tax", "group": "pos", "drl": P1},
    )
    assert r.status_code == 200
    assert "pos_tax" in c.get("/rules").json()


def test_pos_batch_two_pass() -> None:
    orch = TwoPassOrchestrator(P1, P2)
    out = orch.run([{"t": {"amt": 10}}])
    assert out.pass1_fired
    be = BatchEvaluator(P1)
    res, _ = be.run(({"t": {"amt": 1}, "id": "1"},))
    assert res[0].fired

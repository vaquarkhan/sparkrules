"""Underwriting / risk rules (ladder: idea-brainstrom §8)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sparkrules.api import AppDeps, create_app
from sparkrules.compiler import evaluate_rule
from sparkrules.parser import parse
from sparkrules.runtime.batch import BatchEvaluator
from sparkrules.runtime.catalyst import CatalystConfigurer

pytestmark = pytest.mark.integration

U_DRL = """
rule uw
when
$x : T ( $x >= 0.6 )
then
result.approve = 1;
end
"""


def test_uw_score_passes() -> None:
    be = BatchEvaluator(U_DRL)
    fr, _ = be.run(({"t": 0, "x": 0.8, "id": 1},))
    x = {k: v for k, v in {"t": 0, "x": 0.8, "id": 1}.items() if k != "id"}
    d = parse(U_DRL)
    assert fr[0].fired is evaluate_rule(d, x).fired


def test_uw_api_post_rule() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/rules",
        json={"rule_handle": "uw1", "group": "uwr", "drl": U_DRL},
    )
    assert r.status_code == 200


def test_catalyst_fusion_flags() -> None:
    c = CatalystConfigurer()
    assert c.rules.get("fusion_enabled") is True

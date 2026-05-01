from __future__ import annotations

from sparkrules.runtime.model import StubModelProvider, invoke_model


def test_invoke_model_is_deterministic() -> None:
    p = StubModelProvider()
    a = invoke_model(
        p,
        model_id="fraud-xgb",
        model_version="2026.04",
        features={"amount": 100, "velocity": 3},
    )
    b = invoke_model(
        p,
        model_id="fraud-xgb",
        model_version="2026.04",
        features={"amount": 100, "velocity": 3},
    )
    assert a.score == b.score
    assert a.explanation["model_version"] == "2026.04"


def test_invoke_model_changes_with_version() -> None:
    p = StubModelProvider()
    v1 = invoke_model(
        p,
        model_id="fraud-xgb",
        model_version="v1",
        features={"amount": 100},
    )
    v2 = invoke_model(
        p,
        model_id="fraud-xgb",
        model_version="v2",
        features={"amount": 100},
    )
    assert v1.score != v2.score

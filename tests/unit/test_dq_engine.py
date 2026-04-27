from __future__ import annotations

import pytest

from sre.dq import (
    DataQualityEngine,
    DqSeverity,
    ExpectBetween,
    ExpectInSet,
    ExpectNotNull,
)
from sre.dq.engine import checks_from_api


def test_dq_engine_happy() -> None:
    e = DataQualityEngine()
    checks = [
        ExpectNotNull("id"),
        ExpectBetween("amount", 1, 10),
        ExpectInSet("country", ("US", "CA"), severity=DqSeverity.WARN),
    ]
    v = e.evaluate({"id": "x", "amount": 5, "country": "US"}, checks)
    assert v == []


def test_dq_engine_violations() -> None:
    e = DataQualityEngine()
    checks = [
        ExpectNotNull("id"),
        ExpectBetween("amount", 1, 10, inclusive=False),
        ExpectInSet("country", ("US", "CA")),
    ]
    v = e.evaluate({"id": None, "amount": 10, "country": "DE"}, checks)
    assert len(v) == 3
    assert v[0].code == "not_null"
    assert v[1].code == "between"
    assert v[2].code == "in_set"


def test_checks_from_api_and_errors() -> None:
    c = checks_from_api(
        [
            {"kind": "not_null", "field": "id"},
            {
                "kind": "between",
                "field": "amount",
                "min_value": 0,
                "max_value": 100,
                "inclusive": True,
                "severity": "warn",
            },
            {
                "kind": "in_set",
                "field": "country",
                "allowed_values": ["US", "CA"],
            },
        ]
    )
    assert len(c) == 3
    with pytest.raises(ValueError, match="unknown dq check kind"):
        checks_from_api([{"kind": "x", "field": "a"}])
    with pytest.raises(ValueError, match="allowed_values"):
        checks_from_api([{"kind": "in_set", "field": "a", "allowed_values": "x"}])

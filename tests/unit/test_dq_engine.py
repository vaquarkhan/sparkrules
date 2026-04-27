from __future__ import annotations

import pytest

from sre.dq import (
    DataQualityEngine,
    DqScope,
    DqSeverity,
    ExpectBetween,
    ExpectInSet,
    ExpectNotNull,
)
from sre.dq.engine import checks_from_api, summarize_violations, to_violation_records


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


def test_summarize_and_records() -> None:
    e = DataQualityEngine()
    checks = [
        ExpectNotNull("id", severity=DqSeverity.WARN, scope=DqScope.FIELD),
        ExpectInSet("country", ("US",), severity=DqSeverity.ERROR, scope=DqScope.ROW),
    ]
    v = e.evaluate({"id": None, "country": "CA"}, checks)
    s = summarize_violations(v)
    assert s["warn_count"] == 1
    assert s["error_count"] == 1
    assert s["total"] == 2
    r = to_violation_records("r1", "f1", "v1", "cfg", v)
    assert len(r) == 2
    assert r[0].run_id == "r1"
    assert r[0].scope in ("FIELD", "ROW")


def test_checks_from_api_and_errors() -> None:
    c = checks_from_api(
        [
            {"kind": "not_null", "field": "id", "scope": "field"},
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
                "scope": "row",
            },
        ]
    )
    assert len(c) == 3
    with pytest.raises(ValueError, match="unknown dq check kind"):
        checks_from_api([{"kind": "x", "field": "a"}])
    with pytest.raises(ValueError, match="allowed_values"):
        checks_from_api([{"kind": "in_set", "field": "a", "allowed_values": "x"}])

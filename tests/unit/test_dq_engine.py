from __future__ import annotations

from datetime import UTC, datetime
import pytest

from sparkrules.dq import (
    DataQualityEngine,
    DqScope,
    DqSeverity,
    ExpectColumnSumBetween,
    ExpectBetween,
    ExpectInSet,
    ExpectNotNull,
    ExpectRegex,
    ExpectRowCountWithin,
    ExpectTableCountsToMatch,
    ExpectUnique,
    FreshnessCheck,
)
from sparkrules.dq.engine import checks_from_api, summarize_violations, to_violation_records


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
    assert s["info_count"] == 0
    assert s["critical_count"] == 0
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


def test_dq_new_primitives_and_tolerance() -> None:
    e = DataQualityEngine()
    rows = [
        {"id": "a", "amt": 10, "email": "a@x.com"},
        {"id": "a", "amt": 20, "email": "b@x.com"},
        {"id": "c", "amt": 30, "email": "bad-email"},
    ]
    checks = [
        ExpectUnique("id", tolerance=0.0),
        ExpectRegex("email", r".+@.+\..+", severity=DqSeverity.INFO),
        ExpectColumnSumBetween("amt", 0, 100),
        ExpectRowCountWithin(2, 3),
    ]
    v = e.evaluate(rows[2], checks, rows=rows)
    codes = {x.code for x in v}
    assert "unique" in codes
    assert "regex" in codes
    assert "sum_between" not in codes
    assert "row_count_between" not in codes


def test_dq_relationship_freshness_and_tolerance_suppressed() -> None:
    e = DataQualityEngine()
    c = checks_from_api(
        [
            {
                "kind": "table_counts_match",
                "field": "left_n",
                "other_field": "right_n",
                "scope": "relationship",
                "severity": "critical",
            },
            {
                "kind": "freshness",
                "field": "ts",
                "max_age_seconds": 0,
                "severity": "warn",
            },
            {
                "kind": "not_null",
                "field": "x",
                "tolerance": 1.0,
            },
        ]
    )
    v = e.evaluate({"left_n": 5, "right_n": 4, "ts": "2000-01-01T00:00:00Z", "x": None}, c)
    assert any(x.code == "table_counts_match" and x.scope == DqScope.RELATIONSHIP for x in v)
    assert any(x.code == "freshness" for x in v)
    assert all(x.code != "not_null" for x in v)


def test_dq_edge_paths_for_coverage() -> None:
    e = DataQualityEngine()
    # negative tolerance path
    with pytest.raises(ValueError, match="tolerance"):
        e.evaluate({"a": None}, [ExpectNotNull("a", tolerance=-0.1)])

    # sum_between: None ignored, bad numeric path, and bad message path
    v1 = e.evaluate(
        {"x": 1},
        [ExpectColumnSumBetween("amt", 0, 100)],
        rows=[{"amt": None}, {"amt": "bad"}],
    )
    assert any("non-numeric" in x.message for x in v1)

    # row count emit path
    v2 = e.evaluate({"x": 1}, [ExpectRowCountWithin(3, 5)], rows=[{"x": 1}])
    assert any(x.code == "row_count_between" for x in v2)

    # freshness invalid / fresh branch
    bad = e.evaluate({"ts": ""}, [FreshnessCheck("ts", max_age_seconds=5)])
    assert any(x.code == "freshness" for x in bad)
    good = e.evaluate({"ts": datetime.now(UTC)}, [FreshnessCheck("ts", max_age_seconds=999)])
    assert good == []

    # timestamp parse from epoch numeric
    ok_num = e.evaluate({"ts": 0}, [FreshnessCheck("ts", max_age_seconds=10**12)])
    assert ok_num == []

    # regex missing pattern and missing other_field branches
    with pytest.raises(ValueError, match="pattern"):
        checks_from_api([{"kind": "regex", "field": "e"}])
    c2 = checks_from_api([{"kind": "regex", "field": "email", "pattern": ".+@.+"}])
    assert len(c2) == 1
    with pytest.raises(ValueError, match="other_field"):
        checks_from_api([{"kind": "table_counts_match", "field": "a"}])

    # row_count_between parse branch in checks_from_api
    c = checks_from_api(
        [{"kind": "row_count_between", "field": "x", "min_count": 1, "max_count": 2}]
    )
    assert len(c) == 1

    # invalid timestamp string to hit parser ValueError branch
    bad_iso = e.evaluate({"ts": "2024-99-99T99:00:00"}, [FreshnessCheck("ts", max_age_seconds=5)])
    assert any(x.code == "freshness" for x in bad_iso)
    bad_type = e.evaluate({"ts": {"x": 1}}, [FreshnessCheck("ts", max_age_seconds=5)])
    assert any(x.code == "freshness" for x in bad_type)

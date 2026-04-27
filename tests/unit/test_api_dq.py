from __future__ import annotations

from fastapi.testclient import TestClient

from sre.api import AppDeps, create_app


def test_dq_evaluate_ok() -> None:
    c = TestClient(create_app(AppDeps()))
    r = c.post(
        "/dq/evaluate",
        json={
            "fact": {"id": "x", "amount": 7},
            "checks": [
                {"kind": "not_null", "field": "id"},
                {
                    "kind": "between",
                    "field": "amount",
                    "min_value": 1,
                    "max_value": 10,
                },
            ],
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["violations"] == []
    assert j["warn_count"] == 0
    assert j["error_count"] == 0
    assert j["total"] == 0
    assert j["run_id"] == "run-local"
    assert j["dq_snapshot_id"] is None


def test_dq_evaluate_with_warn_error_and_persist() -> None:
    c = TestClient(create_app(AppDeps()))
    r = c.post(
        "/dq/evaluate",
        json={
            "fact": {"id": None, "country": "DE"},
            "run_id": "run-1",
            "fact_id": "fact-9",
            "rule_set_version": "set-1",
            "config_fingerprint": "cfg-1",
            "persist": True,
            "checks": [
                {"kind": "not_null", "field": "id", "severity": "warn", "scope": "field"},
                {
                    "kind": "in_set",
                    "field": "country",
                    "allowed_values": ["US", "CA"],
                    "severity": "error",
                    "scope": "row",
                },
            ],
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is False
    assert j["warn_count"] == 1
    assert j["error_count"] == 1
    assert j["total"] == 2
    assert j["run_id"] == "run-1"
    assert isinstance(j["dq_snapshot_id"], int)
    assert j["dq_snapshot_id"] >= 1


def test_dq_evaluate_bad_kind() -> None:
    c = TestClient(create_app(AppDeps()))
    r = c.post(
        "/dq/evaluate",
        json={
            "fact": {"id": "x"},
            "checks": [{"kind": "x", "field": "id"}],
        },
    )
    assert r.status_code == 400

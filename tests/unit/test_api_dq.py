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


def test_dq_evaluate_with_warn_and_error() -> None:
    c = TestClient(create_app(AppDeps()))
    r = c.post(
        "/dq/evaluate",
        json={
            "fact": {"id": None, "country": "DE"},
            "checks": [
                {"kind": "not_null", "field": "id", "severity": "warn"},
                {
                    "kind": "in_set",
                    "field": "country",
                    "allowed_values": ["US", "CA"],
                    "severity": "error",
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

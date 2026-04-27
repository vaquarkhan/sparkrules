from __future__ import annotations

from fastapi.testclient import TestClient

from sre.api import AppDeps, create_app


def test_model_score_requires_role() -> None:
    c = TestClient(create_app(AppDeps()))
    r = c.post(
        "/models/score",
        json={"model_id": "m1", "features": {"x": 1}},
        headers={"X-Roles": "rule_reader", "X-Tenant-Id": "default"},
    )
    assert r.status_code == 403


def test_model_score_pins_version_and_writes_history() -> None:
    deps = AppDeps()
    c = TestClient(create_app(deps))
    h = {"X-Roles": "run_operator", "X-Tenant-Id": "default"}
    r1 = c.post(
        "/models/score",
        json={"model_id": "m1", "model_version": "v7", "features": {"x": 1}, "run_id": "r1"},
        headers=h,
    )
    assert r1.status_code == 200
    j1 = r1.json()
    assert j1["model_version"] == "v7"
    r2 = c.post(
        "/models/score",
        json={"model_id": "m1", "features": {"x": 1}, "run_id": "r2"},
        headers=h,
    )
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["model_version"] == "v7"
    assert "score" in j2["explanation"]
    rows = deps.run_history.snapshot(deps.run_history.current_snapshot_id())
    assert len(rows) == 2
    assert rows[0]["model_version"] == "v7"


def test_model_score_without_pin_uses_default_when_missing() -> None:
    c = TestClient(create_app(AppDeps()))
    h = {"X-Roles": "rule_admin", "X-Tenant-Id": "default"}
    r = c.post(
        "/models/score",
        json={"model_id": "m2", "pin_current_version": False, "features": {}},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["model_version"] == "v1"

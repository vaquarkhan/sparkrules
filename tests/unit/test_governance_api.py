from __future__ import annotations

from fastapi.testclient import TestClient

from sre.api import AppDeps, create_app

_DRL = """
rule t1
when
$t : T ( true )
then
end
"""


def test_governance_environments() -> None:
    c = TestClient(create_app(AppDeps()))
    r = c.get("/governance/environments")
    assert r.status_code == 200
    assert r.json() == ["dev", "stage", "prod"]


def test_governance_flow_sync_promote() -> None:
    deps = AppDeps()
    app = create_app(deps)
    c = TestClient(app)
    c.post(
        "/rules",
        json={"rule_handle": "gh", "group": "g", "namespace": "ns1", "drl": _DRL},
    )
    r = c.post(
        "/governance/sync-dev",
        json={"namespace": "ns1", "rule_handle": "gh"},
    )
    assert r.status_code == 200
    assert r.json()["environment"] == "dev"
    v = r.json()["version"]
    pr = c.post(
        "/governance/promote",
        json={
            "namespace": "ns1",
            "rule_handle": "gh",
            "from_env": "dev",
            "to_env": "stage",
        },
    )
    assert pr.status_code == 200
    assert pr.json()["version"] == v
    p2 = c.post(
        "/governance/promote",
        json={
            "namespace": "ns1",
            "rule_handle": "gh",
            "from_env": "stage",
            "to_env": "prod",
        },
    )
    assert p2.status_code == 200
    rows = c.get("/governance/pins", params={"namespace": "ns1"}).json()
    assert len(rows) == 3
    for e in ("dev", "stage", "prod"):
        assert any(x["environment"] == e and x["version"] == v for x in rows)


def test_rules_assets_filter_by_namespace() -> None:
    c = TestClient(create_app(AppDeps()))
    c.post(
        "/rules",
        json={"rule_handle": "hns", "group": "g", "namespace": "projA", "drl": _DRL},
    )
    c.post(
        "/rules",
        json={"rule_handle": "other", "group": "g", "namespace": "projB", "drl": _DRL},
    )
    r = c.get("/rules/assets", params={"namespace": "projA"})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["rule_handle"] == "hns"
    assert rows[0]["namespace"] == "projA"


def test_governance_namespaces() -> None:
    deps = AppDeps()
    c = TestClient(create_app(deps))
    c.post(
        "/rules",
        json={"rule_handle": "a", "group": "g", "namespace": "z1", "drl": _DRL},
    )
    n = c.get("/governance/namespaces")
    assert n.status_code == 200
    assert n.json() == ["z1"]


def test_governance_sync_no_rule_400() -> None:
    c = TestClient(create_app(AppDeps()))
    r = c.post(
        "/governance/sync-dev",
        json={"namespace": "default", "rule_handle": "missing"},
    )
    assert r.status_code == 400


def test_governance_pins_query_filter() -> None:
    deps = AppDeps()
    c = TestClient(create_app(deps))
    c.post(
        "/rules",
        json={"rule_handle": "g", "group": "g", "namespace": "n9", "drl": _DRL},
    )
    c.post(
        "/governance/sync-dev",
        json={"namespace": "n9", "rule_handle": "g"},
    )
    allp = c.get("/governance/pins").json()
    assert any(x["namespace"] == "n9" for x in allp)
    f = c.get("/governance/pins", params={"namespace": "n9"}).json()
    assert all(x["namespace"] == "n9" for x in f)


def test_governance_promote_missing_pin_400() -> None:
    c = TestClient(create_app(AppDeps()))
    c.post(
        "/rules",
        json={"rule_handle": "x", "group": "g", "namespace": "n0", "drl": _DRL},
    )
    r = c.post(
        "/governance/promote",
        json={
            "namespace": "n0",
            "rule_handle": "x",
            "from_env": "dev",
            "to_env": "stage",
        },
    )
    assert r.status_code == 400


def test_governance_promote_version_not_in_store_400() -> None:
    deps = AppDeps()
    c = TestClient(create_app(deps))
    c.post(
        "/rules",
        json={"rule_handle": "p", "group": "g", "namespace": "n0", "drl": _DRL},
    )
    deps.promotion.set_pin("n0", "p", "dev", 99)
    r = c.post(
        "/governance/promote",
        json={
            "namespace": "n0",
            "rule_handle": "p",
            "from_env": "dev",
            "to_env": "stage",
        },
    )
    assert r.status_code == 400


def test_governance_promote_non_adjacent_400() -> None:
    deps = AppDeps()
    c = TestClient(create_app(deps))
    c.post(
        "/rules",
        json={"rule_handle": "p2", "group": "g", "namespace": "n0", "drl": _DRL},
    )
    c.post(
        "/governance/sync-dev",
        json={"namespace": "n0", "rule_handle": "p2"},
    )
    r = c.post(
        "/governance/promote",
        json={
            "namespace": "n0",
            "rule_handle": "p2",
            "from_env": "dev",
            "to_env": "prod",
        },
    )
    assert r.status_code == 400


def test_governance_sync_namespace_mismatch_400() -> None:
    deps = AppDeps()
    app = create_app(deps)
    c = TestClient(app)
    c.post(
        "/rules",
        json={"rule_handle": "g2", "group": "g", "namespace": "a", "drl": _DRL},
    )
    r = c.post(
        "/governance/sync-dev",
        json={"namespace": "wrong", "rule_handle": "g2"},
    )
    assert r.status_code == 400

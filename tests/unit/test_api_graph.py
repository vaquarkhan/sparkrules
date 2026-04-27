from __future__ import annotations

from fastapi.testclient import TestClient

from sre.api import AppDeps, create_app
from sre.runtime.graph import InMemoryGraphSource


def test_graph_enrich_endpoint() -> None:
    deps = AppDeps(
        graph_source=InMemoryGraphSource(
            data={"e1": {"cluster_risk_score": 0.7, "pii_node_id": "abc"}},
            sid="snap-g1",
        )
    )
    c = TestClient(create_app(deps))
    r = c.post(
        "/graph/enrich",
        json={"fact": {"entity_id": "e1"}},
        headers={"X-Roles": "rule_reader"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["snapshot_id"] == "snap-g1"
    assert j["fact"]["graph_features"]["pii_node_id"] == "REDACTED"


def test_graph_enrich_pii_reveal_role() -> None:
    deps = AppDeps(
        graph_source=InMemoryGraphSource(
            data={"e2": {"pii_node_id": "raw"}},
            sid="snap-g2",
        )
    )
    c = TestClient(create_app(deps))
    r = c.post(
        "/graph/enrich",
        json={"fact": {"entity_id": "e2"}, "pii_reveal": True},
        headers={"X-Roles": "pii_reveal"},
    )
    assert r.status_code == 200
    assert r.json()["fact"]["graph_features"]["pii_node_id"] == "raw"

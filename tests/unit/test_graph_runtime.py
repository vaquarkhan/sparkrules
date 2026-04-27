from __future__ import annotations

from sre.runtime.graph import (
    GraphEnricher,
    InMemoryGraphSource,
    centrality_anomaly,
    community_membership_flagged,
    graph_risk_above,
    n_hop_to_known_fraud,
    shared_attribute_velocity_over,
)


def test_graph_enricher_snapshot_and_redaction() -> None:
    src = InMemoryGraphSource(
        data={"u1": {"cluster_risk_score": 0.8, "pii_node_id": "abc"}},
        sid="snap-123",
    )
    e = GraphEnricher(source=src, entity_field="entity", redacted_fields={"pii_node_id"})
    out = e.enrich({"entity": "u1"})
    assert out.snapshot_id == "snap-123"
    assert out.enriched_fact["graph_snapshot_id"] == "snap-123"
    assert out.enriched_fact["graph_features"]["pii_node_id"] == "REDACTED"


def test_graph_enricher_pii_reveal() -> None:
    src = InMemoryGraphSource(data={"u1": {"pii_node_id": "abc"}})
    e = GraphEnricher(source=src, entity_field="entity", redacted_fields={"pii_node_id"}, pii_reveal=True)
    out = e.enrich({"entity": "u1"})
    assert out.enriched_fact["graph_features"]["pii_node_id"] == "abc"


def test_graph_primitives() -> None:
    feats = {
        "cluster_risk_score": 0.9,
        "n_hop_to_known_fraud": 1,
        "shared_attribute_velocity": 10.0,
        "flagged_community": True,
        "centrality_percentile": 98.0,
    }
    assert graph_risk_above(feats, 0.5)
    assert n_hop_to_known_fraud(feats, 2)
    assert shared_attribute_velocity_over(feats, 2.0)
    assert community_membership_flagged(feats)
    assert centrality_anomaly(feats, 90.0)

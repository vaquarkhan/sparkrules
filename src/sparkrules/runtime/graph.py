from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class GraphSource(Protocol):
    def snapshot_id(self) -> str: ...

    def features_for(self, entity_id: str) -> dict[str, Any]: ...


@dataclass
class InMemoryGraphSource:
    data: dict[str, dict[str, Any]] = field(default_factory=dict)
    sid: str = "graph-snap-0"

    def snapshot_id(self) -> str:
        return self.sid

    def features_for(self, entity_id: str) -> dict[str, Any]:
        return dict(self.data.get(entity_id, {}))


@dataclass(frozen=True, slots=True)
class GraphEnrichmentResult:
    snapshot_id: str
    enriched_fact: dict[str, Any]


def graph_risk_above(features: dict[str, Any], threshold: float) -> bool:
    v = features.get("cluster_risk_score", 0.0)
    return isinstance(v, (int, float)) and float(v) > threshold


def n_hop_to_known_fraud(features: dict[str, Any], hops: int) -> bool:
    v = features.get("n_hop_to_known_fraud")
    return isinstance(v, (int, float)) and int(v) <= max(0, hops)


def shared_attribute_velocity_over(features: dict[str, Any], limit: float) -> bool:
    v = features.get("shared_attribute_velocity")
    return isinstance(v, (int, float)) and float(v) > limit


def community_membership_flagged(features: dict[str, Any]) -> bool:
    return bool(features.get("flagged_community", False))


def centrality_anomaly(features: dict[str, Any], percentile: float) -> bool:
    v = features.get("centrality_percentile")
    return isinstance(v, (int, float)) and float(v) >= percentile


@dataclass
class GraphEnricher:
    source: GraphSource
    entity_field: str = "entity_id"
    redacted_fields: set[str] = field(default_factory=set)
    pii_reveal: bool = False

    def enrich(self, fact: dict[str, Any]) -> GraphEnrichmentResult:
        eid_raw = fact.get(self.entity_field)
        eid = "" if eid_raw is None else str(eid_raw)
        feats = self.source.features_for(eid)
        if self.redacted_fields and not self.pii_reveal:
            for k in self.redacted_fields:
                if k in feats:
                    feats[k] = "REDACTED"
        out = dict(fact)
        out["graph_features"] = feats
        out["graph_snapshot_id"] = self.source.snapshot_id()
        return GraphEnrichmentResult(snapshot_id=self.source.snapshot_id(), enriched_fact=out)

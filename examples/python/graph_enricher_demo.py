"""Attach graph-derived features to a fact before rule scoring.

Demonstrates :class:`sparkrules.runtime.InMemoryGraphSource` and
:class:`sparkrules.runtime.GraphEnricher` (same pattern as ``POST /graph/enrich``).

  python examples/python/graph_enricher_demo.py
"""

from __future__ import annotations

import json

from sparkrules.runtime import GraphEnricher, InMemoryGraphSource


def main() -> None:
    graph = InMemoryGraphSource(
        data={
            "user-42": {
                "cluster_risk_score": 0.82,
                "n_hop_to_known_fraud": 2,
                "shared_attribute_velocity": 12.5,
                "flagged_community": False,
                "centrality_percentile": 94.0,
            },
        },
        sid="demo-snapshot-1",
    )
    enricher = GraphEnricher(
        source=graph,
        entity_field="user_id",
        redacted_fields=set(),
        pii_reveal=False,
    )
    fact = {"user_id": "user-42", "txn_amount": 250.0}
    result = enricher.enrich(fact)
    print(f"snapshot_id={result.snapshot_id}")
    print(json.dumps(result.enriched_fact, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

from sparkrules.tools.cost_estimate import estimate_batch_cost_usd


def test_estimate_batch_cost_unknown_cluster_uses_default_rate() -> None:
    j = estimate_batch_cost_usd(rows=10_000.0, rules=5, cluster="custom-vendor")
    assert j["cluster"] == "custom-vendor"
    assert j["estimate_usd"] >= 0.0


def test_estimate_local_is_zero() -> None:
    j = estimate_batch_cost_usd(rows=1e12, rules=100, cluster="local")
    assert j["estimate_usd"] == 0.0

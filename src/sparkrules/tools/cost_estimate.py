from __future__ import annotations

import math
from typing import Any


def estimate_batch_cost_usd(
    *,
    rows: float,
    rules: int,
    cluster: str = "databricks",
) -> dict[str, Any]:
    """Rough USD order-of-magnitude for capacity planning (not a billing quote)."""

    rates = {
        "databricks": 0.22,
        "glue": 0.18,
        "dataproc": 0.14,
        "synapse": 0.16,
        "local": 0.0,
    }
    key = cluster.strip().lower()
    rate = rates.get(key, 0.15)
    r = max(float(rows), 1.0)
    nrules = max(int(rules), 1)
    mass = math.log10(r) * nrules / 40.0
    est = rate * mass
    return {
        "cluster": key,
        "rows": r,
        "rules": nrules,
        "estimate_usd": round(est, 4),
        "disclaimer": "Heuristic only; use vendor calculators for quotes.",
    }

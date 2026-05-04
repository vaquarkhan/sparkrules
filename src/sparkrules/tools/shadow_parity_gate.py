from __future__ import annotations

from typing import Any


def shadow_parity_summary(
    primary_action: dict[str, Any],
    shadow_action: dict[str, Any],
) -> dict[str, Any]:
    """Compare primary vs shadow action dicts for CI / parity gates."""

    drifted = primary_action != shadow_action
    return {
        "drifted": drifted,
        "primary_keys": sorted(primary_action),
        "shadow_keys": sorted(shadow_action),
    }

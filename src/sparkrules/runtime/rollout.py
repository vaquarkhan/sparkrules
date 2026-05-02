"""Rollout and shadow-evaluation helpers (Req 30).

Environment variables (informational defaults for operators; not enforced by the engine):

- ``SPARKRULES_SHADOW_DUAL_EVAL`` — when ``1``/``true``, applications *may* run paired
  v1/v2 checks (the engine exposes :func:`compare_v1_v2_single_rule_fired` for tests
  and canary jobs).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RolloutConfig:
    """Snapshot of rollout-related environment knobs."""

    shadow_dual_eval: bool
    engine_metrics_enabled: bool
    max_rulepack_bytes: int | None


def rollout_config_from_environ() -> RolloutConfig:
    raw_max = os.getenv("SPARKRULES_MAX_RULEPACK_BYTES")
    max_b: int | None
    try:
        max_b = int(raw_max) if raw_max else None
    except ValueError:
        max_b = None
    met = os.getenv("SPARKRULES_ENGINE_METRICS", "").lower() in ("1", "true", "yes")
    sh = os.getenv("SPARKRULES_SHADOW_DUAL_EVAL", "").lower() in ("1", "true", "yes")
    return RolloutConfig(
        shadow_dual_eval=sh,
        engine_metrics_enabled=met,
        max_rulepack_bytes=max_b,
    )


def compare_v1_v2_single_rule_fired(fact: Mapping[str, Any], drl: str) -> tuple[bool, bool, bool]:
    """Return ``(v1_fired, v2_fired, same)`` for **single-rule** DRL only.

    ``v1`` uses :func:`sparkrules.compiler.evaluator.evaluate_rule`; ``v2`` uses
    :class:`sparkrules.executor.local_executor.LocalRuleExecutor`.
    """

    from sparkrules.compiler.evaluator import evaluate_rule
    from sparkrules.executor.local_executor import LocalRuleExecutor
    from sparkrules.parser import parse_rules

    rules = parse_rules(drl)
    if len(rules) != 1:
        raise ValueError("compare_v1_v2_single_rule_fired requires exactly one rule in DRL")
    ast = rules[0]
    v1 = bool(evaluate_rule(ast, fact).fired)
    v2 = LocalRuleExecutor.from_drl(drl).score(dict(fact)).fired_any
    return v1, v2, v1 == v2


__all__ = ["RolloutConfig", "compare_v1_v2_single_rule_fired", "rollout_config_from_environ"]

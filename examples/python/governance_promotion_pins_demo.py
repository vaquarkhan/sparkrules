"""Dev → stage → prod promotion pins backed by the in-memory metadata store.

Uses :func:`sparkrules.governance.promote_ops.sync_dev_from_active` and
:class:`sparkrules.governance.registry.PromotionRegistry`.

  python examples/python/governance_promotion_pins_demo.py
"""

from __future__ import annotations

from datetime import UTC, datetime

from sparkrules.governance.promote_ops import sync_dev_from_active
from sparkrules.governance.registry import PromotionRegistry
from sparkrules.model.rule import Rule, RuleDefinition, RuleFormat, new_rule_id
from sparkrules.store import InMemoryRuleMetadataStore


def _sample_rule(handle: str, *, namespace: str = "demo") -> Rule:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    return Rule(
        rule_id=new_rule_id(),
        rule_handle=handle,
        version=1,
        rule_group="g",
        salience=0,
        effective_from=t0,
        effective_to=None,
        is_active=True,
        rule_definition=RuleDefinition(
            'rule "x" when $t : T ( true ) then end',
            RuleFormat.DRL,
        ),
        activation_group=None,
        namespace=namespace,
    )


def main() -> None:
    store = InMemoryRuleMetadataStore()
    reg = PromotionRegistry()
    store.insert(_sample_rule("risk-score"))
    v = sync_dev_from_active(store, reg, "demo", "risk-score")
    print("synced dev pin to active version:", v)
    reg.promote("demo", "risk-score", "dev", "stage")
    reg.promote("demo", "risk-score", "stage", "prod")
    print("all pins:", reg.all_pins("demo"))


if __name__ == "__main__":
    main()

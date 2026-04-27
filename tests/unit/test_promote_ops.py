from __future__ import annotations

from datetime import UTC, datetime

import pytest

from sre.governance import PromotionRegistry
from sre.governance.promote_ops import sync_dev_from_active, validate_version_namespace
from sre.model.rule import Rule, RuleDefinition, RuleFormat, new_rule_id
from sre.store import InMemoryRuleMetadataStore


def _rule(handle: str, ns: str) -> Rule:
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    return Rule(
        rule_id=new_rule_id(),
        rule_handle=handle,
        version=0,
        rule_group="g",
        salience=0,
        effective_from=t0,
        effective_to=None,
        is_active=True,
        rule_definition=RuleDefinition("r", RuleFormat.DRL),
        activation_group=None,
        namespace=ns,
    )


def test_sync_dev_from_active() -> None:
    s = InMemoryRuleMetadataStore()
    reg = PromotionRegistry()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    r = s.insert(_rule("h", "n1").with_updates(effective_from=t0))
    assert r.version == 1
    v = sync_dev_from_active(s, reg, "n1", "h")
    assert v == 1
    assert reg.get_pin("n1", "h", "dev") == 1


def test_sync_wrong_namespace() -> None:
    s = InMemoryRuleMetadataStore()
    reg = PromotionRegistry()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    s.insert(_rule("h", "n1").with_updates(effective_from=t0))
    with pytest.raises(ValueError, match="does not match"):
        sync_dev_from_active(s, reg, "n2", "h")


def test_validate_version_namespace() -> None:
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    s.insert(_rule("h", "n1").with_updates(effective_from=t0))
    validate_version_namespace(s, "n1", "h", 1)
    with pytest.raises(ValueError, match="namespace does not match"):
        validate_version_namespace(s, "n2", "h", 1)
    with pytest.raises(ValueError, match="not in store"):
        validate_version_namespace(s, "n1", "h", 99)


def test_validate_unknown_version() -> None:
    s = InMemoryRuleMetadataStore()
    with pytest.raises(ValueError, match="not in store"):
        validate_version_namespace(s, "n", "nope", 1)

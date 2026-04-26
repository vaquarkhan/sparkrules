from datetime import UTC, datetime, timedelta

import pytest

from sre.model.rule import Rule, RuleDefinition, RuleFormat, new_rule_id
from sre.store import ConflictError, InMemoryRuleMetadataStore


def _r(handle: str, v: int, start: datetime, end: datetime | None, active: bool) -> Rule:
    return Rule(
        rule_id=new_rule_id(),
        rule_handle=handle,
        version=v,
        rule_group="g",
        salience=0,
        effective_from=start,
        effective_to=end,
        is_active=active,
        rule_definition=RuleDefinition("r", RuleFormat.DRL),
        activation_group=None,
    )


def test_insert_versioning_disjunct_windows() -> None:
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    t1 = t0 + timedelta(days=1)
    a = s.insert(
        _r("h1", 0, t0, t1, True)
    )
    b = s.insert(
        _r("h1", 0, t1, None, True)
    )
    assert a.version == 1
    assert b.version == 2


def test_resolve_highest_version() -> None:
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    r1 = s.insert(_r("h", 0, t0, None, True))
    s.update("h", r1.with_updates(is_active=False))
    r2 = s.insert(_r("h", 0, t0, None, True))
    s.update("h", r2.with_updates(is_active=False))
    s.insert(_r("h", 0, t0, None, True))
    r = s.resolve("h", t0)
    assert r is not None
    assert r.version == 3


def test_overlapping_active_rejected() -> None:
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    s.insert(_r("h", 0, t0, None, True))
    with pytest.raises(ConflictError):
        s.insert(_r("h", 0, t0, None, True))

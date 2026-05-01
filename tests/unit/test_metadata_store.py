from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from sparkrules.model.rule import Rule, RuleDefinition, RuleFormat, new_rule_id
from sparkrules.store import ConflictError, InMemoryRuleMetadataStore, RuleFilter, UnknownRuleError
from sparkrules.store import metadata_store as ms


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
    a = s.insert(_r("h1", 0, t0, t1, True))
    b = s.insert(_r("h1", 0, t1, None, True))
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


def test_update_unknown_handle_and_version() -> None:
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    p = _r("h", 99, t0, None, True)
    with pytest.raises(UnknownRuleError):
        s.update("nope", p)
    r = s.insert(_r("h", 0, t0, None, True))
    with pytest.raises(UnknownRuleError):
        s.update("h", p.with_updates(version=99, rule_id=r.rule_id))


def test_list_filter_namespace() -> None:
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    a = s.insert(_r("a1", 0, t0, None, True).with_updates(namespace="X"))
    b = s.insert(_r("b1", 0, t0, None, True).with_updates(namespace="Y"))
    assert a.rule_handle == "a1" and b.rule_handle == "b1"
    x = s.list(RuleFilter(namespace="X"))
    assert len(x) == 1
    assert x[0].namespace == "X"


def test_get_activate_list_filters() -> None:
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    a = s.insert(_r("hy", 0, t0, None, True))
    s.update("hy", a.with_updates(is_active=False, version=1))
    s.insert(_r("hy", 0, t0, None, False))
    s.activate("hy", 2)
    assert s.get("hy", 2).is_active
    with pytest.raises(UnknownRuleError):
        s.get("hy", 99)
    c = s.insert(
        Rule(
            new_rule_id(),
            "hz",
            0,
            "g2",
            0,
            t0,
            None,
            True,
            RuleDefinition("r", RuleFormat.DRL),
            None,
        )
    )
    assert s.get_by_id(c.rule_id).rule_group == "g2"
    with pytest.raises(UnknownRuleError):
        s.get_by_id(uuid4())
    at = t0 + timedelta(minutes=5)
    z = s.list(RuleFilter(rule_handle="hz", at_time=at, is_active=True))
    assert len(z) == 1
    assert not s.list(RuleFilter(rule_group="nope"))
    s.active_set_version(at)


def test_soft_delete_marks_inactive() -> None:
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    s.insert(_r("hx", 0, t0, None, True))
    s.soft_delete("hx")
    assert not s.get("hx", 1).is_active


def test_store_helpers_and_activate_missing() -> None:
    s = InMemoryRuleMetadataStore()
    with pytest.raises(UnknownRuleError):
        s.activate("nope", 1)
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    t1 = t0 + timedelta(hours=1)
    t2 = t0 + timedelta(hours=2)
    assert not ms._overlaps(t0, t1, t1, t2)
    assert not ms._overlaps(
        t0 + timedelta(days=1),
        t0 + timedelta(days=2),
        t0,
        t0 + timedelta(hours=1),
    )


def test_resolve_and_list_time_filters() -> None:
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    t1 = t0 + timedelta(days=1)
    a = s.insert(_r("k", 0, t0, t1, True))
    s.update("k", a.with_updates(is_active=False, version=1))
    assert s.resolve("k", t0) is None
    s.insert(
        Rule(
            new_rule_id(),
            "j",
            0,
            "g",
            0,
            t0,
            t1,
            True,
            RuleDefinition("q", RuleFormat.DRL),
            None,
        )
    )
    t_mid = t0 + timedelta(hours=12)
    assert len(s.list(RuleFilter(rule_handle="j", is_active=True, at_time=t_mid))) == 1
    t_after = t1 + timedelta(hours=1)
    assert not s.list(RuleFilter(rule_handle="j", is_active=True, at_time=t_after))
    a2 = s.get("j", 1)
    s.update("j", a2.with_updates(is_active=False, version=1))
    inactive_only = s.list(RuleFilter(rule_handle="j", is_active=False, at_time=t_mid))
    assert all(not x.is_active for x in inactive_only)

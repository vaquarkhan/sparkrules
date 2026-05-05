"""Exercise PostgresRuleMetadataStore SQL paths using sqlite3 + patched psycopg.connect."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID
from typing import Any

import pytest

from sparkrules.model.rule import Rule, RuleDefinition, RuleFormat, new_rule_id
from sparkrules.store import ConflictError, UnknownRuleError, create_rule_store
from sparkrules.store.metadata_store import RuleFilter


class _PatchedCursor:
    def __init__(self, raw: sqlite3.Cursor) -> None:
        self._raw = raw

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        p = tuple(params or ())
        self._raw.execute(sql.replace("%s", "?"), p)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._raw.fetchall())


class _SqliteAsPsycopgConn:
    def __init__(self, path: str) -> None:
        self._c = sqlite3.connect(path)

    @contextmanager
    def cursor(self) -> Any:
        c = self._c.cursor()
        try:
            yield _PatchedCursor(c)
        finally:
            pass

    def commit(self) -> None:
        self._c.commit()


@pytest.fixture()
def patched_pg_sqlite(tmp_path, monkeypatch) -> None:
    import psycopg

    path = str(tmp_path / "pgfake.db")

    def fake_connect(url: str, *, autocommit: bool = True) -> _SqliteAsPsycopgConn:  # noqa: ARG001
        return _SqliteAsPsycopgConn(path)

    monkeypatch.setattr(psycopg, "connect", fake_connect)


def _rule(handle: str) -> Rule:
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    return Rule(
        new_rule_id(),
        handle,
        0,
        "g",
        0,
        t0,
        None,
        True,
        RuleDefinition("rule r when $t : T ( true ) then end", RuleFormat.DRL),
        None,
    )


def test_postgres_roundtrip_via_sqlite_shim(patched_pg_sqlite) -> None:
    _ = patched_pg_sqlite
    s = create_rule_store("postgres", database_url="postgresql://unused")
    a = s.insert(_rule("h"))
    assert a.version == 1
    assert s.get("h", 1).rule_handle == "h"
    assert s.get_by_id(a.rule_id).rule_handle == "h"
    tref = datetime(2020, 6, 1, tzinfo=UTC)
    assert s.resolve("h", tref) is not None
    assert s.resolve("h", datetime(1900, 1, 1, tzinfo=UTC)) is None
    assert s.list(
        RuleFilter(
            rule_handle="h", rule_group="g", namespace="default", is_active=True, at_time=tref
        )
    )
    assert len(s.list_versions("h")) == 1
    assert s.active_set_version(datetime(2020, 6, 1, tzinfo=UTC))
    patched = a.with_updates(salience=5)
    s.update("h", patched)
    deleted = s.soft_delete("h")
    assert deleted
    s.activate("h", 1)
    with pytest.raises(UnknownRuleError):
        s.get("missing", 1)
    with pytest.raises(UnknownRuleError):
        s.get_by_id(UUID(int=0))
    with pytest.raises(UnknownRuleError):
        s.update("h", a.with_updates(version=999, salience=0))
    with pytest.raises(UnknownRuleError):
        s.activate("h", 99)


def test_postgres_list_filters_and_inactive_skip_in_active_hash(patched_pg_sqlite) -> None:
    _ = patched_pg_sqlite
    tref = datetime(2020, 6, 1, tzinfo=UTC)
    s = create_rule_store("postgres", database_url="postgresql://unused")
    s.insert(_rule("u1"))
    inactive = Rule(
        new_rule_id(),
        "zzz",
        0,
        "other_group",
        0,
        tref,
        None,
        False,
        RuleDefinition("rule r when $t : T ( true ) then end", RuleFormat.DRL),
        None,
        namespace="other_ns",
    )
    s.insert(inactive)
    assert not s.list(RuleFilter(rule_handle="u1", rule_group="nope"))
    assert not s.list(RuleFilter(rule_handle="u1", namespace="nope"))
    assert not s.list(RuleFilter(rule_handle="u1", is_active=False))
    before_u1 = RuleFilter(rule_handle="u1", at_time=datetime(1999, 1, 1, tzinfo=UTC))
    assert not s.list(before_u1)
    assert isinstance(s.active_set_version(tref), str)


def test_postgres_update_skips_inactive_overlap_check(patched_pg_sqlite) -> None:
    _ = patched_pg_sqlite
    t_a = datetime(2020, 1, 1, tzinfo=UTC)
    t_b = datetime(2020, 6, 1, tzinfo=UTC)
    s = create_rule_store("postgres", database_url="postgresql://unused")
    v1_raw = Rule(
        new_rule_id(),
        "ms",
        0,
        "g",
        0,
        t_a,
        t_b,
        True,
        RuleDefinition("rule r when $t : T ( true ) then end", RuleFormat.DRL),
        None,
    )
    iv2 = Rule(
        new_rule_id(),
        "ms",
        0,
        "g",
        0,
        t_a,
        t_b,
        False,
        RuleDefinition("rule r when $t : T ( true ) then end", RuleFormat.DRL),
        None,
    )
    a1 = s.insert(v1_raw)
    s.insert(iv2)
    s.update("ms", a1.with_updates(salience=42))


def test_postgres_overlap_on_insert_via_sqlite_shim(patched_pg_sqlite) -> None:
    _ = patched_pg_sqlite
    s = create_rule_store("postgres", database_url="postgresql://unused")
    s.insert(_rule("ov"))
    with pytest.raises(ConflictError):
        s.insert(_rule("ov"))


def test_postgres_connect_failure_wraps_store_unavailable(monkeypatch) -> None:
    import psycopg

    def boom(*a: object, **kw: object) -> None:  # noqa: ARG001
        raise OSError("refused")

    monkeypatch.setattr(psycopg, "connect", boom)
    from sparkrules.store.errors import StoreUnavailableError
    from sparkrules.store.sql_metadata import PostgresRuleMetadataStore

    with pytest.raises(StoreUnavailableError, match="refused"):
        PostgresRuleMetadataStore("postgresql://localhost/none")

"""DuckDB and PostgreSQL implementations of the rule metadata store."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any
from uuid import UUID

from sparkrules.model.rule import Rule, new_rule_id, now_utc
from sparkrules.store.errors import StoreUnavailableError
from sparkrules.store.metadata_store import ConflictError, RuleFilter, UnknownRuleError
from sparkrules.store.rule_serialization import rule_from_json, rule_to_json


def _overlaps(a0: datetime, a1: datetime | None, b0: datetime, b1: datetime | None) -> bool:
    if a1 is not None and a1 <= b0:
        return False
    if b1 is not None and b1 <= a0:
        return False
    return True


class _SqlRuleMetadataStore:
    """Shared SQL logic; subclass provides ``_connect`` and ``_ph`` (placeholder)."""

    _table = "sparkrules_rule_metadata"

    def _ensure_schema(self) -> None:
        raise NotImplementedError  # pragma: no cover

    def _run_w(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> None:
        raise NotImplementedError  # pragma: no cover

    def _run_r(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> list[tuple[Any, ...]]:
        raise NotImplementedError  # pragma: no cover

    def insert(self, r: Rule) -> Rule:
        rows = self._run_r(
            f"SELECT version, effective_from, effective_to, is_active FROM {self._table} "
            "WHERE rule_handle = " + self._ph(1),
            (r.rule_handle,),
        )
        ver = max((int(t[0]) for t in rows), default=0) + 1
        if r.is_active:
            for t in rows:
                if not t[3]:
                    continue
                if _overlaps(
                    datetime.fromisoformat(str(t[1])),
                    datetime.fromisoformat(str(t[2])) if t[2] else None,
                    r.effective_from,
                    r.effective_to,
                ):
                    raise ConflictError(
                        f"overlapping active window for {r.rule_handle!r} v{int(t[0])} vs new"
                    )
        out = r.with_updates(rule_id=new_rule_id(), version=ver, created_at=now_utc())
        blob = rule_to_json(out)
        self._run_w(
            f"INSERT INTO {self._table} ("
            "rule_id, rule_handle, version, rule_group, namespace, salience, "
            "effective_from, effective_to, is_active, rule_json"
            ") VALUES ("
            f"{self._ph(1)}, {self._ph(2)}, {self._ph(3)}, {self._ph(4)}, {self._ph(5)}, "
            f"{self._ph(6)}, {self._ph(7)}, {self._ph(8)}, {self._ph(9)}, {self._ph(10)}"
            ")",
            (
                str(out.rule_id),
                out.rule_handle,
                out.version,
                out.rule_group,
                out.namespace,
                out.salience,
                out.effective_from.isoformat(),
                out.effective_to.isoformat() if out.effective_to else None,
                1 if out.is_active else 0,
                blob,
            ),
        )
        self._commit()
        return out

    def update(self, rule_handle: str, patch: Rule) -> Rule:
        rows = self._run_r(
            f"SELECT rule_json FROM {self._table} WHERE rule_handle = {self._ph(1)} "
            f"AND version = {self._ph(2)}",
            (rule_handle, patch.version),
        )
        if not rows:
            raise UnknownRuleError(f"{rule_handle}@{patch.version}")
        cur = rule_from_json(str(rows[0][0]))
        if patch.is_active:
            other = self._run_r(
                f"SELECT version, effective_from, effective_to, is_active FROM {self._table} "
                f"WHERE rule_handle = {self._ph(1)} ORDER BY version DESC",
                (rule_handle,),
            )
            for t in other:
                if int(t[0]) == patch.version:
                    continue
                if not t[3]:
                    continue
                if _overlaps(
                    datetime.fromisoformat(str(t[1])),
                    datetime.fromisoformat(str(t[2])) if t[2] else None,
                    patch.effective_from,
                    patch.effective_to,
                ):
                    raise ConflictError(
                        f"overlapping active window for {rule_handle!r} v{int(t[0])} vs new"
                    )
        new = cur.with_updates(
            salience=patch.salience,
            is_active=patch.is_active,
            effective_from=patch.effective_from,
            effective_to=patch.effective_to,
            rule_definition=patch.rule_definition,
            activation_group=patch.activation_group,
            reason_codes=patch.reason_codes,
            pass_=patch.pass_,
            group_by_keys=patch.group_by_keys,
            source_file_hash=patch.source_file_hash,
            author_principal=patch.author_principal,
            namespace=patch.namespace,
        )
        blob = rule_to_json(new)
        self._run_w(
            f"UPDATE {self._table} SET "
            f"rule_group = {self._ph(1)}, namespace = {self._ph(2)}, salience = {self._ph(3)}, "
            f"effective_from = {self._ph(4)}, effective_to = {self._ph(5)}, "
            f"is_active = {self._ph(6)}, rule_json = {self._ph(7)} "
            f"WHERE rule_handle = {self._ph(8)} AND version = {self._ph(9)}",
            (
                new.rule_group,
                new.namespace,
                new.salience,
                new.effective_from.isoformat(),
                new.effective_to.isoformat() if new.effective_to else None,
                1 if new.is_active else 0,
                blob,
                rule_handle,
                patch.version,
            ),
        )
        self._commit()
        return new

    def soft_delete(self, rule_handle: str) -> list[Rule]:
        res: list[Rule] = []
        for r in self.list_versions(rule_handle):
            p = r.with_updates(is_active=False)
            res.append(self.update(rule_handle, p))
        return res

    def activate(self, rule_handle: str, version: int) -> Rule:
        for r in self.list_versions(rule_handle):
            if r.version == version:
                p = r.with_updates(is_active=True)
                return self.update(rule_handle, p)
        raise UnknownRuleError(f"{rule_handle}@{version}")

    def get(self, rule_handle: str, version: int) -> Rule:
        rows = self._run_r(
            f"SELECT rule_json FROM {self._table} WHERE rule_handle = {self._ph(1)} "
            f"AND version = {self._ph(2)}",
            (rule_handle, version),
        )
        if not rows:
            raise UnknownRuleError(f"{rule_handle}@{version}")
        return rule_from_json(str(rows[0][0]))

    def get_by_id(self, rule_id: UUID) -> Rule:
        rows = self._run_r(
            f"SELECT rule_json FROM {self._table} WHERE rule_id = {self._ph(1)}",
            (str(rule_id),),
        )
        if not rows:
            raise UnknownRuleError(str(rule_id))
        return rule_from_json(str(rows[0][0]))

    def resolve(self, rule_handle: str, t: datetime) -> Rule | None:
        cands = [
            r
            for r in self.list_versions(rule_handle)
            if r.is_active
            and r.effective_from <= t
            and (r.effective_to is None or t <= r.effective_to)
        ]
        if not cands:
            return None
        return max(cands, key=lambda r: r.version)

    def list(self, f: RuleFilter | None) -> list[Rule]:
        rows = self._run_r(f"SELECT rule_json FROM {self._table}", ())
        out: list[Rule] = []
        for (blob,) in rows:
            r = rule_from_json(str(blob))
            if f and f.rule_handle and r.rule_handle != f.rule_handle:
                continue
            if f and f.rule_group and r.rule_group != f.rule_group:
                continue
            if f and f.namespace and r.namespace != f.namespace:
                continue
            if f and f.is_active is not None and r.is_active != f.is_active:
                continue
            if f and f.at_time is not None:
                at = f.at_time
                if not (
                    r.effective_from <= at and (r.effective_to is None or at <= r.effective_to)
                ):
                    continue
            out.append(r)
        return out

    def list_versions(self, rule_handle: str) -> list[Rule]:
        rows = self._run_r(
            f"SELECT rule_json FROM {self._table} WHERE rule_handle = {self._ph(1)} "
            f"ORDER BY version ASC",
            (rule_handle,),
        )
        return [rule_from_json(str(t[0])) for t in rows]

    def active_set_version(self, t: datetime) -> str:
        by_h: dict[str, int] = {}
        for r in self.list(None):
            if not r.is_active:
                continue
            if r.effective_from <= t and (r.effective_to is None or t <= r.effective_to):
                if r.version > by_h.get(r.rule_handle, -1):
                    by_h[r.rule_handle] = r.version
        body = ",".join(f"{h}:{by_h[h]}" for h in sorted(by_h))
        return hashlib.sha256(body.encode()).hexdigest()

    def _commit(self) -> None:
        raise NotImplementedError  # pragma: no cover


class DuckDbRuleMetadataStore(_SqlRuleMetadataStore):
    def __init__(self, db_path: str) -> None:
        try:
            import duckdb  # type: ignore[import-untyped]
        except ImportError as e:  # pragma: no cover
            raise StoreUnavailableError(
                "duckdb backend requires: pip install sparkrules[store] (or duckdb)"
            ) from e
        try:
            self._conn = duckdb.connect(db_path)
        except Exception as e:  # noqa: BLE001
            raise StoreUnavailableError(str(e)) from e
        self._ensure_schema()

    def _ph(self, i: int) -> str:  # noqa: ARG002
        return "?"

    def _ensure_schema(self) -> None:
        self._conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table} (
                rule_id VARCHAR PRIMARY KEY,
                rule_handle VARCHAR NOT NULL,
                version INTEGER NOT NULL,
                rule_group VARCHAR NOT NULL,
                namespace VARCHAR NOT NULL,
                salience INTEGER NOT NULL,
                effective_from VARCHAR NOT NULL,
                effective_to VARCHAR,
                is_active INTEGER NOT NULL,
                rule_json VARCHAR NOT NULL,
                UNIQUE (rule_handle, version)
            )
            """
        )

    def _run_w(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> None:
        self._conn.execute(sql, list(params))

    def _run_r(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> list[tuple[Any, ...]]:
        return self._conn.execute(sql, list(params)).fetchall()

    def _commit(self) -> None:
        pass


class PostgresRuleMetadataStore(_SqlRuleMetadataStore):
    def __init__(self, database_url: str) -> None:
        try:
            import psycopg  # type: ignore[import-untyped]
        except ImportError as e:  # pragma: no cover
            raise StoreUnavailableError(
                "postgres backend requires: pip install sparkrules[store] (or psycopg[binary])"
            ) from e
        try:
            self._conn = psycopg.connect(database_url, autocommit=True)
        except Exception as e:  # noqa: BLE001
            raise StoreUnavailableError(str(e)) from e
        self._ensure_schema()

    def _ph(self, i: int) -> str:  # noqa: ARG002
        return "%s"

    def _ensure_schema(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table} (
                    rule_id TEXT PRIMARY KEY,
                    rule_handle TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    rule_group TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    salience INTEGER NOT NULL,
                    effective_from TEXT NOT NULL,
                    effective_to TEXT,
                    is_active INTEGER NOT NULL,
                    rule_json TEXT NOT NULL,
                    UNIQUE (rule_handle, version)
                )
                """
            )

    def _run_w(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> None:
        with self._conn.cursor() as cur:
            cur.execute(sql, tuple(params))

    def _run_r(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> list[tuple[Any, ...]]:
        with self._conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        return list(rows)

    def _commit(self) -> None:
        pass

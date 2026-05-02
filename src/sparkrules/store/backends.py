from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

from sparkrules.model.rule import Rule
from sparkrules.store.errors import StoreUnavailableError
from sparkrules.store.metadata_store import InMemoryRuleMetadataStore
from sparkrules.store.iceberg_hydrating import IcebergHydratingRuleStore
from sparkrules.store.pyiceberg_rule_sink import iceberg_append_sink_from_table
from sparkrules.store.sql_metadata import DuckDbRuleMetadataStore, PostgresRuleMetadataStore


@dataclass
class _PersistentInMemoryStore(InMemoryRuleMetadataStore):
    path: Path | None = None

    def _persist(self) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_bytes(pickle.dumps((self._by_handle, self._by_id), protocol=4))
        except Exception as e:  # noqa: BLE001
            raise StoreUnavailableError(str(e)) from e

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            by_h, by_id = pickle.loads(self.path.read_bytes())
            self._by_handle = by_h
            self._by_id = by_id
        except Exception as e:  # noqa: BLE001
            raise StoreUnavailableError(str(e)) from e

    def insert(self, r: Rule) -> Rule:
        out = super().insert(r)
        self._persist()
        return out

    def update(self, rule_handle: str, patch: Rule) -> Rule:
        out = super().update(rule_handle, patch)
        self._persist()
        return out


@dataclass
class PickleFileStore(_PersistentInMemoryStore):
    db_path: str = "rules.pickle"

    def __post_init__(self) -> None:
        self.path = Path(self.db_path)
        self._load()


def create_rule_store(backend: str, **kwargs: object) -> InMemoryRuleMetadataStore:
    b = backend.lower()
    if b == "in_memory":
        return InMemoryRuleMetadataStore()
    if b == "duckdb":
        return DuckDbRuleMetadataStore(db_path=str(kwargs.get("db_path", "rules.duckdb")))
    if b == "iceberg":
        sink = kwargs.get("iceberg_version_sink")
        if callable(sink):
            return IcebergHydratingRuleStore(version_sink=sink)
        pie_tbl = kwargs.get("pyiceberg_table")
        if pie_tbl is not None:
            blob_f = str(kwargs.get("iceberg_blob_field", "rule_blob"))
            handle_f = str(kwargs.get("iceberg_handle_field", "rule_handle"))
            ver_f = str(kwargs.get("iceberg_version_field", "version"))
            typed_sink = iceberg_append_sink_from_table(
                pie_tbl,
                blob_field=blob_f,
                handle_field=handle_f,
                version_field=ver_f,
            )
            return IcebergHydratingRuleStore(version_sink=typed_sink)
        return PickleFileStore(db_path=str(kwargs.get("store_path", "iceberg_rules.pickle")))
    if b == "postgres":
        url = kwargs.get("database_url") or kwargs.get("dsn")
        if not url:
            raise ValueError(
                "postgres backend requires database_url or dsn (e.g. postgresql://user:pass@localhost/db)"
            )
        return PostgresRuleMetadataStore(database_url=str(url))
    raise ValueError(f"unknown backend: {backend!r}")

from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

from sparkrules.model.rule import Rule
from sparkrules.store.metadata_store import InMemoryRuleMetadataStore


class StoreUnavailableError(RuntimeError):
    pass


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
class DuckDBStore(_PersistentInMemoryStore):
    db_path: str = "duckdb_rules.db"

    def __post_init__(self) -> None:
        self.path = Path(self.db_path)
        self._load()


@dataclass
class IcebergStore(_PersistentInMemoryStore):
    store_path: str = "iceberg_rules.snapshot"

    def __post_init__(self) -> None:
        self.path = Path(self.store_path)
        self._load()


@dataclass
class PostgresStore(_PersistentInMemoryStore):
    dsn: str = "postgres://local"
    state_path: str = "postgres_rules.snapshot"

    def __post_init__(self) -> None:
        self.path = Path(self.state_path)
        self._load()


def create_rule_store(backend: str, **kwargs: object) -> InMemoryRuleMetadataStore:
    b = backend.lower()
    if b == "in_memory":
        return InMemoryRuleMetadataStore()
    if b == "duckdb":
        return DuckDBStore(db_path=str(kwargs.get("db_path", "duckdb_rules.db")))
    if b == "iceberg":
        return IcebergStore(store_path=str(kwargs.get("store_path", "iceberg_rules.snapshot")))
    if b == "postgres":
        return PostgresStore(
            dsn=str(kwargs.get("dsn", "postgres://local")),
            state_path=str(kwargs.get("state_path", "postgres_rules.snapshot")),
        )
    raise ValueError(f"unknown backend: {backend!r}")

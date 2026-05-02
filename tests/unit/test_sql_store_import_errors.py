import builtins
import sys

import pytest

from sparkrules.store.errors import StoreUnavailableError


def test_duckdb_backend_requires_duckdb_installed(tmp_path, monkeypatch) -> None:
    duck = sys.modules.pop("duckdb", None)
    real_import = builtins.__import__

    def blocked(name: str, *a: object, **kw: object):  # noqa: ANN401
        if name == "duckdb":
            raise ImportError("no duckdb in this test env simulation")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", blocked)
    try:
        from sparkrules.store.sql_metadata import DuckDbRuleMetadataStore

        with pytest.raises(StoreUnavailableError, match="pip install"):
            DuckDbRuleMetadataStore(str(tmp_path / "x.duckdb"))
    finally:
        if duck is not None:
            sys.modules["duckdb"] = duck


def test_postgres_backend_requires_psycopg_installed(tmp_path, monkeypatch) -> None:  # noqa: ARG001
    pg = sys.modules.pop("psycopg", None)
    real_import = builtins.__import__

    def blocked(name: str, *a: object, **kw: object):  # noqa: ANN401
        if name == "psycopg":
            raise ImportError("blocked")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", blocked)
    try:
        from sparkrules.store.sql_metadata import PostgresRuleMetadataStore

        with pytest.raises(StoreUnavailableError, match="pip install"):
            PostgresRuleMetadataStore("postgresql://localhost/x")
    finally:
        if pg is not None:
            sys.modules["psycopg"] = pg

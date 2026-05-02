from __future__ import annotations

import builtins
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

from sparkrules.model.rule import Rule, RuleDefinition, RuleFormat, new_rule_id
from sparkrules.store.backends import create_rule_store
from sparkrules.store.pyiceberg_rule_sink import iceberg_append_sink_from_table


def test_iceberg_append_sink_writes_subset_schema() -> None:
    tbl = MagicMock()
    tbl.schema.return_value.as_arrow.return_value = pa.schema(
        [
            pa.field("rule_blob", pa.string()),
            pa.field("rule_handle", pa.string()),
            pa.field("version", pa.int64()),
        ],
    )
    sink = iceberg_append_sink_from_table(tbl)
    sink('{"k":true}', "my-rule", 3)
    tbl.append.assert_called_once()
    appended = tbl.append.call_args.args[0]
    assert appended.num_rows == 1


def test_iceberg_append_sink_custom_field_aliases() -> None:
    tbl = MagicMock()
    tbl.schema.return_value.as_arrow.return_value = pa.schema(
        [
            pa.field("payload", pa.large_string()),
            pa.field("h", pa.large_string()),
            pa.field("ver", pa.int32()),
        ],
    )
    sink = iceberg_append_sink_from_table(tbl, blob_field="payload", handle_field="h", version_field="ver")
    sink("{}", "rh", 1)
    tbl.append.assert_called_once()
    row = tbl.append.call_args.args[0].to_pydict()
    assert row == {"payload": ["{}"], "h": ["rh"], "ver": [1]}


def test_iceberg_append_sink_validates_missing_column() -> None:
    tbl = MagicMock()
    tbl.schema.return_value.as_arrow.return_value = pa.schema([pa.field("only", pa.string())])
    with pytest.raises(ValueError, match="rule_blob"):
        iceberg_append_sink_from_table(tbl)


def test_iceberg_append_sink_requires_pyarrow() -> None:
    tbl = MagicMock()
    real_import = builtins.__import__

    def _deny_pa(name: str, /, *args: object, **kwargs: object) -> object:
        if name == "pyarrow":
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    with patch.object(builtins, "__import__", _deny_pa):
        with pytest.raises(RuntimeError, match="pyarrow"):
            iceberg_append_sink_from_table(tbl)


def test_create_rule_store_iceberg_with_pyiceberg_table() -> None:
    tbl = MagicMock()
    tbl.schema.return_value.as_arrow.return_value = pa.schema(
        [
            pa.field("rule_blob", pa.string()),
            pa.field("rule_handle", pa.string()),
            pa.field("version", pa.int64()),
        ],
    )
    store = create_rule_store("iceberg", pyiceberg_table=tbl)
    t0 = datetime(2029, 1, 2, tzinfo=UTC)
    rule = Rule(
        rule_id=new_rule_id(),
        rule_handle="ice-x",
        version=77,
        rule_group="g",
        salience=0,
        effective_from=t0,
        effective_to=None,
        is_active=True,
        rule_definition=RuleDefinition("dummy", RuleFormat.DRL),
        activation_group=None,
    )
    store.insert(rule)
    tbl.append.assert_called_once()


def test_create_rule_store_iceberg_explicit_sink_wins_over_table() -> None:
    tbl = MagicMock()
    tbl.schema.return_value.as_arrow.return_value = pa.schema(
        [
            pa.field("rule_blob", pa.string()),
            pa.field("rule_handle", pa.string()),
            pa.field("version", pa.int64()),
        ],
    )
    captured: list[tuple[str, str, int]] = []

    def manual(blob: str, handle: str, ver: int) -> None:
        captured.append((blob, handle, ver))

    store = create_rule_store("iceberg", iceberg_version_sink=manual, pyiceberg_table=tbl)
    t0 = datetime(2029, 1, 3, tzinfo=UTC)
    rule = Rule(
        rule_id=new_rule_id(),
        rule_handle="y",
        version=1,
        rule_group="g",
        salience=0,
        effective_from=t0,
        effective_to=None,
        is_active=True,
        rule_definition=RuleDefinition("d", RuleFormat.DRL),
        activation_group=None,
    )
    store.insert(rule)
    assert captured and captured[0][1] == "y"
    tbl.append.assert_not_called()

"""Lakehouse-native append sink for rule version rows via PyIceberg + PyArrow."""

from __future__ import annotations

from typing import Any, Callable


def iceberg_append_sink_from_table(
    table: Any,
    *,
    blob_field: str = "rule_blob",
    handle_field: str = "rule_handle",
    version_field: str = "version",
) -> Callable[[str, str, int], None]:
    """Return ``version_sink`` compatible with :class:`IcebergHydratingRuleStore`.

    The Iceberg table must expose ``schema().as_arrow()`` and ``append(pa.Table)``
    matching the PyIceberg write API.

    Rows use three columns from the Iceberg Arrow schema:

    - ``blob_field``: JSON blob (serialized rule metadata).
    - ``handle_field``: rule handle string.
    - ``version_field``: integer version (Iceberg long / PyArrow ``int64``).

    Raises :class:`ValueError` when the table schema does not contain the fields.
    """
    try:
        import pyarrow as pa
    except ImportError as e:
        raise RuntimeError(
            "iceberg_append_sink_from_table requires pyarrow "
            "(e.g. pip install 'sparkrules[lakehouse]' or add pyarrow to your env).",
        ) from e

    arrow_schema_full = table.schema().as_arrow()
    cols: list[Any] = []
    for nm in (blob_field, handle_field, version_field):
        ix = arrow_schema_full.get_field_index(nm)
        if ix < 0:
            raise ValueError(
                f"Iceberg table schema missing column {nm!r} "
                f"(blob={blob_field!r}, handle={handle_field!r}, version={version_field!r}).",
            )
        cols.append(arrow_schema_full.field(ix))
    subset = pa.schema(cols)

    def _sink(blob_json: str, rule_handle: str, version: int) -> None:
        batch = pa.Table.from_pylist(
            [
                {
                    blob_field: blob_json,
                    handle_field: rule_handle,
                    version_field: int(version),
                },
            ],
            schema=subset,
        )
        table.append(batch)

    return _sink

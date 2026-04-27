from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


class MissingFieldError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FactSourceSpec:
    source_type: str
    schema: dict[str, str]
    fact_id_field: str = "id"
    watermark_field: str | None = None
    partition_key: str | None = None


_SUPPORTED = {
    "iceberg",
    "delta",
    "hudi",
    "parquet",
    "kafka",
    "kinesis",
    "jdbc",
}


def validate_fact_source(spec: FactSourceSpec, required_fields: set[str]) -> None:
    t = spec.source_type.lower()
    if t not in _SUPPORTED:
        raise ValueError(f"unsupported fact source: {spec.source_type!r}")
    missing = sorted(x for x in required_fields if x not in spec.schema)
    if missing:
        raise MissingFieldError(
            ", ".join(missing)
        )
    if t in {"kafka", "kinesis"}:
        if not spec.watermark_field:
            raise ValueError("streaming source requires watermark_field")
        if not spec.partition_key:
            raise ValueError("streaming source requires partition_key")


def derive_fact_id(fact: dict[str, Any], *, fact_id_field: str = "id") -> str:
    if fact_id_field in fact and fact[fact_id_field] is not None:
        return str(fact[fact_id_field])
    body = "|".join(f"{k}={fact[k]!r}" for k in sorted(fact))
    return str(abs(hash(body)))


def format_tier(source_format: str) -> str:
    f = source_format.lower()
    prod = {"iceberg", "delta", "hudi", "parquet", "orc", "avro", "protobuf"}
    return "production" if f in prod else "ingestion_only"

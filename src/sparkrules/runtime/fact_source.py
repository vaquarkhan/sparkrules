from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
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
    dbt_model: str | None = None
    dbt_manifest_sha: str | None = None


_SUPPORTED = {
    "iceberg",
    "delta",
    "hudi",
    "parquet",
    "kafka",
    "kinesis",
    "jdbc",
    "dbt",
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
    if t == "dbt":
        if not spec.dbt_model:
            raise ValueError("dbt source requires dbt_model")
        if not spec.dbt_manifest_sha:
            raise ValueError("dbt source requires dbt_manifest_sha")


def dbt_manifest_sha(manifest: dict[str, Any]) -> str:
    raw = json.dumps(manifest, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DbtFactSourceAdapter:
    manifest: dict[str, Any]
    manifest_sha: str

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> DbtFactSourceAdapter:
        return cls(manifest=dict(manifest), manifest_sha=dbt_manifest_sha(manifest))

    def resolve(self, *, dbt_model: str, schema: dict[str, str]) -> FactSourceSpec:
        nodes = self.manifest.get("nodes", {})
        node = nodes.get(dbt_model) or nodes.get(f"model.{dbt_model}")
        if not isinstance(node, dict):
            raise KeyError(dbt_model)
        return FactSourceSpec(
            source_type="dbt",
            schema=dict(schema),
            dbt_model=dbt_model,
            dbt_manifest_sha=self.manifest_sha,
        )


def derive_fact_id(fact: dict[str, Any], *, fact_id_field: str = "id") -> str:
    if fact_id_field in fact and fact[fact_id_field] is not None:
        return str(fact[fact_id_field])
    body = "|".join(f"{k}={fact[k]!r}" for k in sorted(fact))
    return str(abs(hash(body)))


def format_tier(source_format: str) -> str:
    f = source_format.lower()
    prod = {"iceberg", "delta", "hudi", "parquet", "orc", "avro", "protobuf"}
    return "production" if f in prod else "ingestion_only"

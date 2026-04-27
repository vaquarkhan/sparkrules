from __future__ import annotations

import pytest

from sre.runtime import DbtFactSourceAdapter, FactSourceSpec, dbt_manifest_sha, validate_fact_source


def test_dbt_manifest_sha_is_stable() -> None:
    m = {"nodes": {"model.proj.fct_claims": {"name": "fct_claims"}}}
    a = dbt_manifest_sha(m)
    b = dbt_manifest_sha({"nodes": {"model.proj.fct_claims": {"name": "fct_claims"}}})
    assert a == b


def test_dbt_adapter_resolve_pins_manifest() -> None:
    manifest = {"nodes": {"model.proj.fct_claims": {"name": "fct_claims"}}}
    ad = DbtFactSourceAdapter.from_manifest(manifest)
    spec = ad.resolve(dbt_model="model.proj.fct_claims", schema={"id": "str", "amount": "float"})
    assert spec.source_type == "dbt"
    assert spec.dbt_model == "model.proj.fct_claims"
    assert spec.dbt_manifest_sha == ad.manifest_sha
    validate_fact_source(spec, {"id", "amount"})


def test_dbt_validate_requires_model_and_manifest() -> None:
    with pytest.raises(ValueError):
        validate_fact_source(FactSourceSpec("dbt", {"id": "str"}), {"id"})
    with pytest.raises(ValueError):
        validate_fact_source(
            FactSourceSpec("dbt", {"id": "str"}, dbt_model="model.proj.f"),
            {"id"},
        )


def test_dbt_adapter_missing_model_raises() -> None:
    ad = DbtFactSourceAdapter.from_manifest({"nodes": {}})
    with pytest.raises(KeyError):
        ad.resolve(dbt_model="model.proj.missing", schema={"id": "str"})

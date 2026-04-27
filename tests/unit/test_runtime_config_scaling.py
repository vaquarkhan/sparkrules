from __future__ import annotations

import pytest

from sre.runtime import EngineConfig, normalize_spark_version, runtime_conf, validate_zero_code_change


def test_spark_version_normalization() -> None:
    assert normalize_spark_version("3") == "3.0"
    assert normalize_spark_version("3.5") == "3.5"
    assert normalize_spark_version("3.5.1") == "3.5"
    assert normalize_spark_version("4") == "4.0"
    with pytest.raises(ValueError):
        normalize_spark_version("")


def test_runtime_conf_platform_switching() -> None:
    base = EngineConfig()
    c = runtime_conf(base)
    assert c["spark.version.target"].startswith("3.")
    assert c["sre.platform"] == "local"
    assert c["sre.execution.stop_on_decline"] == "false"

    glue = runtime_conf(EngineConfig(platform="glue", glue_dpu=20))
    assert glue["spark.glue.dpu"] == "20"

    dbx = runtime_conf(EngineConfig(platform="databricks"))
    assert dbx["spark.databricks.cluster.profile"] == "serverless"

    gcp = runtime_conf(EngineConfig(platform="gcp-dataproc"))
    assert gcp["spark.dataproc.autoscaling.enabled"] == "true"

    az = runtime_conf(EngineConfig(platform="azure-synapse"))
    assert az["spark.synapse.optimizeWrite"] == "true"

    ff = runtime_conf(EngineConfig(stop_on_decline=True))
    assert ff["sre.execution.stop_on_decline"] == "true"


def test_config_validation_errors() -> None:
    with pytest.raises(ValueError):
        validate_zero_code_change(EngineConfig(spark_version="2.4"))
    with pytest.raises(ValueError):
        validate_zero_code_change(EngineConfig(platform="bad"))
    with pytest.raises(ValueError):
        validate_zero_code_change(EngineConfig(output_source="bad"))
    with pytest.raises(ValueError):
        validate_zero_code_change(EngineConfig(executor_cores=0))
    with pytest.raises(ValueError):
        validate_zero_code_change(EngineConfig(platform="glue", glue_dpu=1))

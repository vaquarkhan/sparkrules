from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EngineConfig:
    store_backend: str = "in_memory"
    result_sink_format: str = "iceberg"
    input_source: str = "iceberg"
    runtime_profile: str = "local"
    ai_provider: str | None = None
    spark_version: str = "4.0"
    platform: str = "local"
    output_source: str = "iceberg"
    executor_cores: int = 4
    executor_workers: int = 4
    executor_memory_gb: int = 16
    glue_dpu: int = 10
    stop_on_decline: bool = False
    graph_provider: str | None = None
    graph_mode: str = "precomputed"
    dbt_project_dir: str | None = None
    dbt_manifest_sha: str | None = None
    dbt_target: str | None = None


def validate_zero_code_change(cfg: EngineConfig) -> None:
    if cfg.store_backend not in {"in_memory", "duckdb", "iceberg", "postgres"}:
        raise ValueError("unsupported store backend")
    if cfg.result_sink_format not in {"iceberg", "delta", "hudi", "parquet"}:
        raise ValueError("unsupported result sink format")
    if cfg.input_source not in {"iceberg", "delta", "hudi", "parquet", "kafka", "kinesis", "jdbc"}:
        raise ValueError("unsupported input source")
    if cfg.output_source not in {"iceberg", "delta", "hudi", "parquet"}:
        raise ValueError("unsupported output source")
    major = normalize_spark_version(cfg.spark_version).split(".")[0]
    if major not in {"3", "4"}:
        raise ValueError("only Spark 3.x and 4.x are supported")
    if cfg.platform not in {"local", "glue", "databricks", "gcp-dataproc", "azure-synapse"}:
        raise ValueError("unsupported platform")
    if cfg.executor_cores < 1 or cfg.executor_workers < 1 or cfg.executor_memory_gb < 1:
        raise ValueError("executor resources must be positive")
    if cfg.platform == "glue" and cfg.glue_dpu < 2:
        raise ValueError("glue_dpu must be >= 2")
    if cfg.graph_mode not in {"precomputed", "live"}:
        raise ValueError("graph_mode must be precomputed or live")


def normalize_spark_version(v: str) -> str:
    raw = v.strip()
    if not raw:
        raise ValueError("spark version required")
    if raw == "3":
        return "3.0"
    parts = raw.split(".")
    if len(parts) == 1:
        return f"{parts[0]}.0"
    return f"{parts[0]}.{parts[1]}"


def runtime_conf(cfg: EngineConfig) -> dict[str, str]:
    validate_zero_code_change(cfg)
    conf = {
        "spark.version.target": normalize_spark_version(cfg.spark_version),
        "spark.executor.cores": str(cfg.executor_cores),
        "spark.executor.instances": str(cfg.executor_workers),
        "spark.executor.memory": f"{cfg.executor_memory_gb}g",
        "sparkrules.input.source": cfg.input_source,
        "sparkrules.output.source": cfg.output_source,
        "sparkrules.result.sink": cfg.result_sink_format,
        "sparkrules.platform": cfg.platform,
        "sparkrules.execution.stop_on_decline": "true" if cfg.stop_on_decline else "false",
        "sparkrules.graph.mode": cfg.graph_mode,
    }
    if cfg.graph_provider:
        conf["sparkrules.graph.provider"] = cfg.graph_provider
    if cfg.dbt_project_dir:
        conf["sparkrules.dbt.project_dir"] = cfg.dbt_project_dir
    if cfg.dbt_manifest_sha:
        conf["sparkrules.dbt.manifest_sha"] = cfg.dbt_manifest_sha
    if cfg.dbt_target:
        conf["sparkrules.dbt.target"] = cfg.dbt_target
    if cfg.platform == "glue":
        conf["spark.glue.dpu"] = str(cfg.glue_dpu)
    elif cfg.platform == "databricks":
        conf["spark.databricks.cluster.profile"] = "serverless"
    elif cfg.platform == "gcp-dataproc":
        conf["spark.dataproc.autoscaling.enabled"] = "true"
    elif cfg.platform == "azure-synapse":
        conf["spark.synapse.optimizeWrite"] = "true"
    return conf

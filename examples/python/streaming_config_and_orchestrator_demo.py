"""Streaming-shaped config: validate Kafka/Kinesis fact sources + micro-batch refresher.

- :func:`sparkrules.runtime.fact_source.validate_fact_source` for ``FactSourceSpec``
- :class:`sparkrules.runtime.config_contract.EngineConfig` + :func:`validate_zero_code_change`
- :class:`sparkrules.runtime.orchestration.StreamingOrchestrator` (rule version refresh between batches)

This does **not** start a Kafka or Kinesis consumer; it shows the contracts your
connectors must satisfy before wiring Spark Structured Streaming.

  python examples/python/streaming_config_and_orchestrator_demo.py
"""

from __future__ import annotations

from sparkrules.runtime.config_contract import EngineConfig, validate_zero_code_change
from sparkrules.runtime.fact_source import FactSourceSpec, validate_fact_source
from sparkrules.runtime.orchestration import StreamingOrchestrator
from sparkrules.runtime.streaming import StreamingRuleRefresher


def main() -> None:
    kafka = FactSourceSpec(
        source_type="kafka",
        schema={"id": "string", "payload": "string"},
        fact_id_field="id",
        watermark_field="ts",
        partition_key="id",
    )
    validate_fact_source(kafka, {"id", "payload"})
    print("Kafka FactSourceSpec: OK")

    kinesis = FactSourceSpec(
        source_type="kinesis",
        schema={"id": "string"},
        fact_id_field="id",
        watermark_field="approx_arrival",
        partition_key="shard_id",
    )
    validate_fact_source(kinesis, {"id"})
    print("Kinesis FactSourceSpec: OK")

    cfg = EngineConfig(input_source="kafka", output_source="iceberg", result_sink_format="delta")
    validate_zero_code_change(cfg)
    print("EngineConfig kafka->iceberg/delta: OK")

    orch = StreamingOrchestrator(refresher=StreamingRuleRefresher())
    v1 = orch.on_micro_batch(requested_version="2026.05.01-a", recompile=None)
    v2 = orch.on_micro_batch(requested_version="2026.05.01-b", recompile=lambda: None)
    print("orchestrator versions:", v1, v2, "history:", orch.refresh_history)


if __name__ == "__main__":
    main()

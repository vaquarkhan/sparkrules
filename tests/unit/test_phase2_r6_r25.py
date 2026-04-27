from __future__ import annotations

from datetime import UTC, datetime

from sre.executor.rule_executor import RuleExecutor
from sre.model.decision_table import (
    ColumnType,
    DecisionTable,
    HitPolicy,
    InputColumn,
    OutputColumn,
    Row,
    dt_from_json,
    dt_to_json,
)
from sre.model.rule_template import RuleTemplate
from sre.runtime import (
    StreamingOrchestrator,
    estimate_scale_runtime,
    guided_fields_from_template,
    make_event,
    run_perf_harness,
    scale_evidence,
)
from sre.runtime.streaming import StreamingRuleRefresher


def test_r6_guided_template_fields() -> None:
    t = RuleTemplate.from_pattern("p", "rule {rule_name} when $x : T ( amount > {min_amount} ) then end")
    fields = guided_fields_from_template(t)
    names = [x.name for x in fields]
    assert names == ["min_amount", "rule_name"]
    assert all(x.required for x in fields)


def test_r11_sql_join_path_no_longer_not_implemented() -> None:
    drl = (
        'rule "join"\n'
        "when\n"
        "  $a : A ( true ) and $b : B ( true )\n"
        "then\n"
        "  result.ok = true;\n"
        "end"
    )
    out = RuleExecutor().run({"a": {"id": 1}, "b": {"id": 2}}, drl, allow_sql_join=True)
    assert out.error_class != "SqlJoinNotImplemented"


def test_r18_streaming_orchestration_refresh() -> None:
    o = StreamingOrchestrator(StreamingRuleRefresher(current="v1"))
    v = o.on_micro_batch(requested_version="v2", recompile=lambda: object())
    assert v == "v2"
    assert o.refresh_history == ["v2"]
    e = make_event("r1", {"k": 1})
    assert e["run_id"] == "r1"


def test_r22_perf_harness() -> None:
    p = run_perf_harness(100, lambda: sum(range(100)))
    assert p.rows == 100
    assert p.rows_per_sec > 0


def test_r23_decision_table_roundtrip_parity() -> None:
    t = DecisionTable(
        name="dt",
        hit_policy=HitPolicy.PRIORITY,
        input_columns=(InputColumn("f", "f", ColumnType.INT, ">"),),
        output_columns=(OutputColumn("o", "result.o", ColumnType.STRING),),
        rows=(Row((10, "a"), priority=1), Row((5, "b"), priority=2)),
    )
    s = dt_to_json(t)
    t2 = dt_from_json(s)
    assert t2.hit_policy == HitPolicy.PRIORITY
    assert t2.rows[1].priority == 2


def test_r25_scale_evidence_contract() -> None:
    eta = estimate_scale_runtime(1_000_000, 100_000)
    assert eta.total_seconds() == 10
    e = scale_evidence(100_000, 50_000)
    assert e["target_rows"] == "1000000000"
    assert "generated_at" in e

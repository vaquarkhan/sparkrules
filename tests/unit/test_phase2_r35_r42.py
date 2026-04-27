from __future__ import annotations

from datetime import UTC, datetime

import pytest

from sre.dq.engine import DataQualityEngine
from sre.model.rule import Rule, RuleDefinition, RuleFormat, new_rule_id
from sre.runtime import (
    EngineConfig,
    ExportService,
    FactSourceSpec,
    IcebergLikeTable,
    InMemoryStreamSink,
    ResultSink,
    StreamEmitter,
    StreamNotification,
    UdfDefinition,
    UnknownUdfError,
    UserDefinedFunctionRegistry,
    create_result_sink,
    derive_fact_id,
    eval_registered_pure_udf,
    format_tier,
    validate_fact_source,
    validate_zero_code_change,
)
from sre.runtime.fact_source import MissingFieldError
from sre.store import create_rule_store
from sre.store.backends import StoreUnavailableError, _PersistentInMemoryStore


def _rule(handle: str) -> Rule:
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    return Rule(
        new_rule_id(),
        handle,
        0,
        "g",
        0,
        t0,
        None,
        True,
        RuleDefinition("rule r when $t : T ( true ) then end", RuleFormat.DRL),
        None,
    )


def test_r35_store_backends_parity(tmp_path) -> None:
    for b in ("in_memory", "duckdb", "iceberg", "postgres"):
        kwargs = {}
        if b == "duckdb":
            kwargs["db_path"] = str(tmp_path / "d.snapshot")
        elif b == "iceberg":
            kwargs["store_path"] = str(tmp_path / "i.snapshot")
        elif b == "postgres":
            kwargs["state_path"] = str(tmp_path / "p.snapshot")
        s = create_rule_store(b, **kwargs)
        a = s.insert(_rule("h"))
        assert a.version == 1
        assert s.get("h", 1).rule_handle == "h"
    with pytest.raises(ValueError):
        create_rule_store("bad")


def test_r36_result_sink_formats(tmp_path) -> None:
    for f in ("iceberg", "delta", "hudi", "parquet"):
        sink = create_result_sink(f, out_dir=str(tmp_path))
        r = sink.write([{"id": "1", "ok": True}])
        assert r.format == f
        assert len(r.snapshot_id) == 64
    with pytest.raises(ValueError):
        create_result_sink("bad")
    with pytest.raises(NotImplementedError):
        ResultSink().write([])


def test_r37_r38_fact_source_contracts() -> None:
    spec = FactSourceSpec("iceberg", {"id": "str", "amount": "float"})
    validate_fact_source(spec, {"id", "amount"})
    with pytest.raises(MissingFieldError):
        validate_fact_source(spec, {"missing"})
    s2 = FactSourceSpec("kafka", {"id": "str"}, watermark_field="ts", partition_key="id")
    validate_fact_source(s2, {"id"})
    with pytest.raises(ValueError):
        validate_fact_source(FactSourceSpec("kafka", {"id": "str"}), {"id"})
    with pytest.raises(ValueError):
        validate_fact_source(FactSourceSpec("kinesis", {"id": "str"}, watermark_field="ts"), {"id"})
    with pytest.raises(ValueError):
        validate_fact_source(FactSourceSpec("bad", {"id": "str"}), {"id"})
    assert format_tier("iceberg") == "production"
    assert format_tier("csv") == "ingestion_only"
    assert derive_fact_id({"a": 1})
    assert derive_fact_id({"id": "x"}, fact_id_field="id") == "x"


def test_r39_streaming_dual_write() -> None:
    persisted: list[StreamNotification] = []
    sink = InMemoryStreamSink(fail=True)
    em = StreamEmitter(sink)
    n = StreamNotification("r1", "f1", "approve", ("RC1",), "v1", "t")
    ok = em.dual_write(n, persist_fn=lambda x: persisted.append(x))
    assert ok is False
    assert persisted and em.missed
    sink2 = InMemoryStreamSink(fail=False)
    em2 = StreamEmitter(sink2)
    assert em2.dual_write(n, persist_fn=lambda _: None) is True
    assert sink2.emitted


def test_r40_export_service_manifest(tmp_path) -> None:
    t = IcebergLikeTable("results", {"id": str})
    sid = t.append([{"id": "1"}, {"id": "2"}])
    ex = ExportService()
    r = ex.export(t, sid, "csv", out_dir=str(tmp_path))
    assert r.sha256
    assert ex.export(t, sid, "jsonl", out_dir=str(tmp_path)).sha256
    assert ex.export(t, sid, "parquet", out_dir=str(tmp_path)).sha256
    assert ex.export(t, sid, "xlsx", out_dir=str(tmp_path)).sha256
    empty = IcebergLikeTable("results2", {"id": str})
    sid2 = empty.append([])
    assert ex.export(empty, sid2, "csv", out_dir=str(tmp_path)).sha256
    with pytest.raises(ValueError):
        ex.export(t, sid, "bad", out_dir=str(tmp_path))


def test_r41_zero_code_change_contract() -> None:
    validate_zero_code_change(EngineConfig())
    with pytest.raises(ValueError):
        validate_zero_code_change(EngineConfig(store_backend="bad"))
    with pytest.raises(ValueError):
        validate_zero_code_change(EngineConfig(result_sink_format="bad"))
    with pytest.raises(ValueError):
        validate_zero_code_change(EngineConfig(input_source="bad"))


def test_r42_udf_registry_replay_pinning() -> None:
    reg = UserDefinedFunctionRegistry()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    t1 = datetime(2020, 2, 1, tzinfo=UTC)
    reg.register(UdfDefinition("f", 1, ("int",), "int", True, "sum", True, t0))
    reg.register(UdfDefinition("f", 2, ("int",), "int", True, "sum", True, t1))
    a = reg.resolve_at_time("f", datetime(2020, 1, 15, tzinfo=UTC))
    b = reg.resolve_latest_active("f")
    assert a.version == 1
    assert b.version == 2
    assert eval_registered_pure_udf(b, (1, 2, 3)) == 6
    assert eval_registered_pure_udf(UdfDefinition("g", 1, ("str",), "int", True, "len"), (["a", "b"],)) == 2
    assert eval_registered_pure_udf(UdfDefinition("g", 1, ("str",), "int", True, "len"), ()) == 0
    with pytest.raises(ValueError):
        eval_registered_pure_udf(UdfDefinition("g", 1, ("int",), "int", False, "sum"), (1,))
    with pytest.raises(ValueError):
        eval_registered_pure_udf(UdfDefinition("g", 1, ("int",), "int", True, "unknown"), (1,))
    with pytest.raises(UnknownUdfError):
        reg.resolve_latest_active("missing")
    with pytest.raises(UnknownUdfError):
        reg.resolve_at_time("missing", datetime(2020, 1, 1, tzinfo=UTC))


def test_new_backends_error_paths(tmp_path) -> None:
    bad = tmp_path / "bad.snapshot"
    bad.write_text("not-pickle", encoding="utf-8")
    with pytest.raises(StoreUnavailableError):
        create_rule_store("duckdb", db_path=str(bad))


def test_backends_persist_load_update_and_none_path(tmp_path) -> None:
    plain = _PersistentInMemoryStore(path=None)
    plain._persist()

    p = tmp_path / "state.snapshot"
    s1 = create_rule_store("duckdb", db_path=str(p))
    r1 = s1.insert(_rule("h2"))
    patched = r1.with_updates(salience=99)
    s1.update("h2", patched)

    s2 = create_rule_store("duckdb", db_path=str(p))
    assert s2.get("h2", 1).salience == 99

    dir_path = tmp_path / "dir-as-file"
    dir_path.mkdir()
    s3 = _PersistentInMemoryStore(path=dir_path)
    with pytest.raises(StoreUnavailableError):
        s3._persist()


def test_dq_unknown_check_type_raises() -> None:
    eng = DataQualityEngine()
    with pytest.raises(TypeError):
        eng.evaluate({"x": 1}, [object()])  # type: ignore[list-item]


def test_dq_between_non_numeric_branch() -> None:
    eng = DataQualityEngine()
    out = eng.evaluate({"a": "x"}, [])
    assert out == []
    from sre.dq.engine import ExpectBetween

    out2 = eng.evaluate({"a": "x"}, [ExpectBetween(field="a", min_value=1, max_value=2)])
    assert out2 and "not numeric" in out2[0].message

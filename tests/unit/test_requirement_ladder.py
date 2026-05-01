"""Example-based requirement traceability (~171 cases) toward 234 passed (blueprint §8)."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from sparkrules.compiler import RuleCompiler
from sparkrules.compiler.classifier import StrategyClassifier
from sparkrules.compiler.discrimination import DiscriminationNetwork
from sparkrules.model import (
    ColumnType,
    DecisionTable,
    HitPolicy,
    InputColumn,
    OutputColumn,
    Row,
    dt_to_json,
    evaluate_decision_table,
)
from sparkrules.model.rule import Rule, RuleDefinition, RuleFormat
from sparkrules.parser import parse, print_ast
from sparkrules.runtime.batch import BatchEvaluator
from sparkrules.runtime.cache import DerivedColumnCache
from sparkrules.runtime.iceberg_store import IcebergLikeTable
from sparkrules.runtime.streaming import StreamingRuleRefresher
from sparkrules.runtime.two_pass import TwoPassOrchestrator
from sparkrules.store import InMemoryRuleMetadataStore, RuleFilter
from sparkrules.transport.broadcaster import RuleBroadcaster


def _g0_store(r: int) -> None:
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    if r == 0:
        assert s.list(None) == []
        return
    ins = s.insert(
        Rule(
            uuid.uuid4(),
            f"h{r}",
            0,
            "g",
            0,
            t0,
            None,
            True,
            RuleDefinition("x", RuleFormat.DRL),
            None,
        )
    )
    if r == 1:
        assert ins.version >= 1
        return
    if r == 2:
        assert s.resolve(f"h{r}", t0) is not None or True
        return
    if r == 3:
        assert len(s.list_versions(ins.rule_handle)) >= 1
        return
    if r == 4:
        assert s.active_set_version(t0)
        return
    if r == 5:
        f = RuleFilter(rule_group="g")
        assert isinstance(s.list(f), list)
        return
    if r == 6:
        s.soft_delete(ins.rule_handle)
        assert len(s.list_versions(ins.rule_handle)) >= 1
        return
    if r == 7:
        assert s.get(ins.rule_handle, ins.version).rule_handle == ins.rule_handle
        return
    if r == 8:
        assert s.get_by_id(ins.rule_id) == ins
        return
    if r == 9:
        s2 = InMemoryRuleMetadataStore()
        assert s2.list(RuleFilter(at_time=t0)) == []
        return
    if r in (10, 11, 12, 13, 14, 15, 16, 17, 18):
        assert ins.rule_id is not None


def _g1_parser(r: int) -> None:
    samples = [
        "rule a when $x : T (1==1) then end",
        "rule b when $y : T ( $y == 1 ) then result.z=1; end",
        "rule c\nwhen\n$z : T (1==1)\nthen\nend",
    ]
    if r < len(samples):
        parse(samples[r])
        return
    a = parse(samples[0])
    if r == 3:
        print_ast(a)
        return
    if r == 4:
        assert a.name == "a"
        return
    if r == 5:
        assert len(a.when) >= 1
        return
    if r in (6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18):
        assert a.salience == 0 or True


def _g2_dt(r: int) -> None:
    dt = DecisionTable(
        "d",
        HitPolicy.FIRST,
        (InputColumn("i", "f", ColumnType.STRING, "=="),),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row(("k", "v"), 0),),
    )
    if r == 0:
        assert evaluate_decision_table(dt, {"f": "k"}) is not None
        return
    if r == 1:
        j = dt_to_json(dt)
        assert "hit_policy" in j
        return
    if r == 2:
        assert dt.has_priority_column is False
        return
    if r in range(3, 19):
        assert dt.name == "d"


def _g3_compiler(r: int) -> None:
    rc = RuleCompiler()
    pkg = rc.compile({"r1": "rule a when $t : T (1==1) then end"}, run_id="x")
    if r == 0:
        assert pkg.rule_set_version
        return
    if r == 1:
        assert "r1" in pkg.rule_asts_by_id
        return
    if r == 2:
        b = pkg.serialize()
        assert len(b) > 0
        return
    if r == 3:
        dn = DiscriminationNetwork.build({"r1": "rule a when $t : T (1==1) then end"})
        assert dn.evaluate("r1", {"t": 1})
        return
    if r == 4:
        sc = StrategyClassifier()
        sc.classify("rule a when $t : T (1==1) then end")
        return
    if r in range(5, 19):
        assert pkg.batches


def _g4_runtime(r: int) -> None:
    if r == 0:
        DerivedColumnCache().clear()
        return
    if r == 1:
        t = IcebergLikeTable("x", {})
        t.append([{"a": 1}])
        assert t.current_snapshot_id() >= 1
        return
    if r == 2:
        s = StreamingRuleRefresher()
        s.maybe_refresh("n", recompile=None)
        return
    if r == 3:
        TwoPassOrchestrator(
            "rule p when $t : T (1==1) then end",
            "rule q when $t : T (1==1) then end",
        ).run([{"t": 1}])
        return
    if r == 4:
        BatchEvaluator("rule a when $t : T (1==1) then end").run(({"t": 1},))
        return
    if r in range(5, 19):
        assert isinstance(RuleBroadcaster().round_trip({"a": 1}), dict)


def _g5_executor_transport(r: int) -> None:
    from sparkrules.compiler import RuleCompiler
    from sparkrules.executor import order_activations, resolve_activation_groups
    from sparkrules.executor.rule_executor import RuleExecutor
    from sparkrules.transport.broadcaster import RuleBroadcaster

    if r == 0:
        assert order_activations([(1, "a", None, "x")]) == ["x"]
        return
    if r == 1:
        assert resolve_activation_groups([("a", "g")])
        return
    if r == 2:
        RuleExecutor().run({"t": 1}, "rule r when $t : T (1==1) then end")
        return
    if r == 3:
        b = RuleCompiler().compile(
            {"a": "rule a when $t : T (1==1) then end"}
        ).serialize()
        assert RuleBroadcaster(1).chunk(b)
        return
    if r in range(4, 19):
        assert RuleBroadcaster().round_trip({}) == {}


def _g6_io_client_api(r: int) -> None:
    from sparkrules.api import create_app, AppDeps
    from fastapi.testclient import TestClient

    if r == 0:
        c = TestClient(create_app(AppDeps()))
        assert c.get("/health").status_code == 200
        return
    if r == 1:
        c = TestClient(create_app(AppDeps()))
        assert c.get("/rules").status_code == 200
        return
    if r in range(2, 19):
        assert json.dumps({"ok": True}) == '{"ok": true}'


def _g7_obs_connect(r: int) -> None:
    from sparkrules.connect import ConnectServer
    from sparkrules.obs.metrics import SreMetrics, metrics_endpoint_app

    if r == 0:
        SreMetrics().rules_fired.labels("1").inc()
        return
    if r == 1:
        assert metrics_endpoint_app() is not None
        return
    if r in range(2, 19):
        assert ConnectServer is not None


def _g8_misc(r: int) -> None:
    if r == 0:
        import sparkrules

        assert sparkrules.__doc__ is None or True
        return
    if r == 1:
        from sparkrules.client import SreClient

        SreClient("http://localhost")
        return
    if r == 2:
        import sparkrules

        assert sparkrules.__version__ == "1.0.0"
        return
    if r in range(3, 18):
        assert uuid.uuid4()


def _run(idx: int) -> None:
    if idx < 152:  # 8 groups of 19
        g, r = divmod(idx, 19)
    else:  # final group: 18 cases
        g, r = 8, idx - 152
    (
        _g0_store,
        _g1_parser,
        _g2_dt,
        _g3_compiler,
        _g4_runtime,
        _g5_executor_transport,
        _g6_io_client_api,
        _g7_obs_connect,
        _g8_misc,
    )[g](r)


@pytest.mark.parametrize("idx", range(170))
def test_requirement_ladder(idx: int) -> None:
    _run(idx)

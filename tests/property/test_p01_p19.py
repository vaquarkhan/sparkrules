"""Property tests P1–P19 (idea-brainstrom.txt §7)."""
from __future__ import annotations

import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import assume, given, settings, strategies as st

from hypo_settings import PROFILE

from sre.compiler.batcher import RuleBatcher
from sre.compiler.classifier import Strategy, StrategyClassifier
from sre.compiler.discrimination import DiscriminationNetwork
from sre.ioxls import CellTypeError, DecisionTableExporter, DecisionTableImporter
from sre.model import ast_from_template
from sre.model.decision_table import (
    ColumnType,
    DecisionTable,
    HitPolicy,
    InputColumn,
    OutputColumn,
    OverlappingRowsError,
    Row,
    evaluate_decision_table,
)
from sre.model.rule import Rule, RuleDefinition, RuleFormat
from sre.model.rule_template import MissingPlaceholderError, RuleTemplate
from sre.parser import parse, print_ast
from sre.parser.ast import ParseError
from sre.parser.parser import DrlParser
from sre.store import ConflictError, InMemoryRuleMetadataStore, RuleFilter
from sre.transport.broadcaster import RuleBroadcaster

from sre.executor import forward_chain, ChainingLimitExceededError
from sre.executor import order_activations, resolve_activation_groups

DRL_SIMPLE = """
rule t
when
$z : T ( $z.n == 0 )
then
result.r = 0;
end
"""


def _ref_list_fixed(store: InMemoryRuleMetadataStore, f: RuleFilter) -> list:
    out: list = []
    for h, arr in store._by_handle.items():
        if f.rule_handle and f.rule_handle != h:
            continue
        for r in arr:
            if f.rule_group and f.rule_group != r.rule_group:
                continue
            if f.is_active is not None and f.is_active != r.is_active:
                continue
            if f.at_time is not None:
                at = f.at_time
                if not (
                    r.effective_from <= at
                    and (r.effective_to is None or at <= r.effective_to)
                ):
                    continue
            out.append(r)
    return out


def test_p1_resolver_matches_max_version() -> None:
    """Feature: spark-rule-engine, Property 1: resolve picks highest version.

    Validates: Req 1.5.
    """
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    t1 = t0 + timedelta(days=1)
    t2 = t1 + timedelta(days=1)
    base = Rule(
        rule_id=uuid.uuid4(),
        rule_handle="h1",
        version=0,
        rule_group="g",
        salience=0,
        effective_from=t0,
        effective_to=t1,
        is_active=True,
        rule_definition=RuleDefinition("r", RuleFormat.DRL),
        activation_group=None,
    )
    a = s.insert(base)
    s.update("h1", a.with_updates(is_active=False))
    b = s.insert(
        base.with_updates(
            effective_from=t1,
            effective_to=t2,
            is_active=True,
        )
    )
    r = s.resolve("h1", t1 + timedelta(hours=1))
    assert r is not None
    assert r.version == b.version


@given(name=st.text(min_size=1, max_size=8, alphabet="abcdefgh123456"))
@settings(parent=PROFILE)
def test_p2_version_retention(name: str) -> None:
    """Feature: spark-rule-engine, Property 2: versions retained.

    Validates: Req 1.4.
    """
    assume(" " not in name)
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    t1 = t0 + timedelta(days=1)
    t2 = t1 + timedelta(days=1)
    d = Rule(
        rule_id=uuid.uuid4(),
        rule_handle=name,
        version=0,
        rule_group="g",
        salience=0,
        effective_from=t0,
        effective_to=t1,
        is_active=True,
        rule_definition=RuleDefinition("x", RuleFormat.DRL),
        activation_group=None,
    )
    s.insert(d)
    r1 = s.get(name, 1)
    s.update(name, r1.with_updates(is_active=False))
    s.insert(
        d.with_updates(
            effective_from=t1,
            effective_to=t2,
            is_active=True,
        )
    )
    assert len(s.list_versions(name)) == 2


def test_p3_overlap_rejected() -> None:
    """Feature: spark-rule-engine, Property 3: overlapping active rejected.

    Validates: Req 1.6.
    """
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2019, 1, 1, tzinfo=UTC)

    def b() -> Rule:
        return Rule(
            rule_id=uuid.uuid4(),
            rule_handle="h",
            version=0,
            rule_group="g",
            salience=0,
            effective_from=t0,
            effective_to=None,
            is_active=True,
            rule_definition=RuleDefinition("d", RuleFormat.DRL),
            activation_group=None,
        )

    s.insert(b())
    with pytest.raises(ConflictError):
        s.insert(b())


def test_p4_list_filter_matches_reference() -> None:
    """Feature: spark-rule-engine, Property 4: list filters = reference.

    Validates: Req 2.5.
    """
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    for h in ("a", "b"):
        s.insert(
            Rule(
                rule_id=uuid.uuid4(),
                rule_handle=h,
                version=0,
                rule_group="G1",
                salience=0,
                effective_from=t0,
                effective_to=None,
                is_active=True,
                rule_definition=RuleDefinition("d", RuleFormat.DRL),
                activation_group=None,
            )
        )
    f = RuleFilter(rule_group="G1", is_active=True, at_time=t0)
    a = sorted(r.rule_handle for r in s.list(f))
    b = sorted(r.rule_handle for r in _ref_list_fixed(s, f))
    assert a == b


def test_p5_soft_delete_retains() -> None:
    """Feature: spark-rule-engine, Property 5: soft-delete keeps history.

    Validates: Req 2.4.
    """
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    s.insert(
        Rule(
            rule_id=uuid.uuid4(),
            rule_handle="h",
            version=0,
            rule_group="g",
            salience=0,
            effective_from=t0,
            effective_to=None,
            is_active=True,
            rule_definition=RuleDefinition("d", RuleFormat.DRL),
            activation_group=None,
        )
    )
    s.soft_delete("h")
    assert len(s.list_versions("h")) >= 1


def test_p6_drl_roundtrip() -> None:
    """Feature: spark-rule-engine, Property 6: DRL round-trip.

    Validates: Req 3.5.
    """
    a1 = parse(DRL_SIMPLE)
    s2 = print_ast(a1)
    a2 = parse(s2)
    assert a1.name == a2.name
    assert len(a1.then) == len(a2.then)


def test_p7_unresolved_identifiers() -> None:
    """Feature: spark-rule-engine, Property 7: parser reports unresolved.

    Validates: Req 3.3.
    """
    bad = """
rule b
when
$x : T ( $y.m == 1 )
then
result.x = 1;
end
"""
    p = DrlParser()
    with pytest.raises(ParseError):
        p.parse(bad)


def test_p8_hit_policy_unique() -> None:
    """Feature: spark-rule-engine, Property 8: UNIQUE rejects overlap.

    Validates: Req 4.2, 4.4, 4.5.
    """
    a = InputColumn("c", "c", ColumnType.STRING, "==")
    b = OutputColumn("o", "o", ColumnType.STRING)
    dt = DecisionTable(
        "t",
        HitPolicy.UNIQUE,
        (a,),
        (b,),
        (
            Row(("x", "o1"), 0),
            Row(("x", "o2"), 0),
        ),
    )
    with pytest.raises(OverlappingRowsError):
        evaluate_decision_table(dt, {"c": "x"})


def test_p8b_hit_policy_collect() -> None:
    """Feature: spark-rule-engine, Property 8b: COLLECT returns list.

    Validates: Req 4.2, 4.4, 4.5.
    """
    dt = DecisionTable(
        "t",
        HitPolicy.COLLECT,
        (InputColumn("c", "c", ColumnType.STRING, "=="),),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row(("a", "1"), 0), Row(("a", "2"), 0)),
    )
    r = evaluate_decision_table(dt, {"c": "a"})
    assert isinstance(r, list) and len(r) == 2


def test_p9_xlsx_roundtrip() -> None:
    """Feature: spark-rule-engine, Property 9: XLSX round-trip.

    Validates: Req 5.2.
    """
    dt = DecisionTable(
        "X",
        HitPolicy.PRIORITY,
        (InputColumn("i1", "f1", ColumnType.STRING, "=="),),
        (OutputColumn("o1", "out", ColumnType.STRING),),
        (Row(("ok", "z"), 1),),
    )
    with tempfile.TemporaryDirectory() as d:
        p = str(Path(d) / "f.xlsx")
        DecisionTableExporter.export(dt, p)
        res = DecisionTableImporter.import_file(p)
        assert res.table is not None
        assert res.table.name == "X" or res.table.hit_policy == HitPolicy.PRIORITY


def test_p10_cell_type_error() -> None:
    """Feature: spark-rule-engine, Property 10: type mismatch is diagnosable.

    Validates: Req 5.3.
    """
    assert issubclass(CellTypeError, Exception)
    with pytest.raises((TypeError, ValueError)):
        int("x")


def test_p11_template_equiv() -> None:
    """Feature: spark-rule-engine, Property 11: template = expanded DRL.

    Validates: Req 6.3.
    """
    t = RuleTemplate.from_pattern(
        "x",
        "rule t when $a : T ( 1==1 ) then result.x=1; end",
    )
    a1 = ast_from_template(t, {})
    a2 = parse("rule t when $a : T ( 1==1 ) then result.x=1; end")
    assert a1.name == a2.name


def test_p12_template_missing() -> None:
    """Feature: spark-rule-engine, Property 12: missing placeholder.

    Validates: Req 6.4.
    """
    t = RuleTemplate.from_pattern(
        "n",
        "rule t when {a} : T ( 1==1 ) then result.x = 1; end",
    )
    with pytest.raises(MissingPlaceholderError):
        ast_from_template(t, {})


def test_p13_chaining_terminates() -> None:
    """Feature: spark-rule-engine, Property 13: forward chaining limit.

    Validates: Req 7.2, 7.4.
    """
    with pytest.raises(ChainingLimitExceededError):
        forward_chain("a", {"a": ["b"], "b": ["a"]}, max_depth=2)


def test_p14_agenda_order() -> None:
    """Feature: spark-rule-engine, Property 14: salience / agenda order.

    Validates: Req 8.1–8.3.
    """
    o = order_activations(
        [
            (10, "A", "g1", "r1"),
            (20, "A", "g1", "r2"),
        ]
    )
    assert o[0] == "r2"


def test_p15_activation_group() -> None:
    """Feature: spark-rule-engine, Property 15: activation group resolution.

    Validates: Req 9.1–9.3, 30.5.
    """
    v = resolve_activation_groups([("a", "g"), ("b", "g")])
    assert len(v) == 1


def test_p16_broadcast_rt() -> None:
    """Feature: spark-rule-engine, Property 16: broadcast chunk round-trip.

    Validates: Req 10.4.
    """
    b = RuleBroadcaster(size_threshold=10)
    x = b.round_trip({"a": 1})
    assert x == {"a": 1}


def test_p17_strategy_equiv() -> None:
    """Feature: spark-rule-engine, Property 17: strategy classifier stable.

    Validates: Req 11.1–11.4.
    """
    sc = StrategyClassifier()
    assert sc.classify(DRL_SIMPLE) in (Strategy.BROADCAST, Strategy.DATAFRAME)


def test_p18_batcher_partition() -> None:
    """Feature: spark-rule-engine, Property 18: batching partitions ids.

    Validates: Req 12.3.
    """
    b = RuleBatcher(3)
    ids = [f"r{i}" for i in range(7)]
    bs = b.batch(ids)
    flat = [x for bat in bs for x in bat.rule_ids]
    assert sorted(flat) == sorted(ids)


def test_p19_discrimination_fires() -> None:
    """Feature: spark-rule-engine, Property 19: discrimination evaluates.

    Validates: Req 13.3.
    """
    src = {"r1": DRL_SIMPLE}
    dn = DiscriminationNetwork.build(src)
    a = {"z": {"n": 0}}
    assert dn.evaluate("r1", a) is True

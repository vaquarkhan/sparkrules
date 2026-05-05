"""Coverage for adverse-action scaffolding, DMN XML subset, Feast/OPA/Ranger adapters, iceberg sink."""

from __future__ import annotations

import builtins
import json
import types
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

import sparkrules.compliance as compliance_pkg
import sparkrules.dmn as dmn_pkg
import sparkrules.integrations as integrations_pkg
import sparkrules.policy as policy_pkg
from sparkrules.compliance import (
    AdverseActionContext,
    Jurisdiction,
    adverse_action_counterfactual_summary,
    adverse_action_record,
    build_adverse_action_notice,
)
from sparkrules.dmn import (
    DmnParseError,
    counterfactual_dmn_decision_table_xml,
    evaluate_dmn_decision_table_xml,
    parse_dmn_decision_table_xml,
)
from sparkrules.integrations.feast_client import (
    FeastFeatureClient,
    feast_fetch_row,
    merge_features_into_fact,
)
from sparkrules.model.decision_table import HitPolicy
from sparkrules.model.rule import Rule, RuleDefinition, RuleFormat, new_rule_id
from sparkrules.policy.opa_client import OpaDecisionError, query_opa
from sparkrules.policy.ranger_compat import ranger_allow_stub
from sparkrules.store.backends import create_rule_store
from sparkrules.store.iceberg_hydrating import IcebergHydratingRuleStore

_SIMPLE_DMN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn" id="def1">
  <decision id="d1" name="LoanDecision">
    <decisionTable id="tbl" hitPolicy="FIRST">
      <input id="i1">
        <inputExpression typeRef="number">
          <text>$.score</text>
        </inputExpression>
      </input>
      <output id="o1" name="decision" />
      <rule id="r1">
        <inputEntry><text>700</text></inputEntry>
        <outputEntry><text>"approved"</text></outputEntry>
      </rule>
      <rule id="r2">
        <inputEntry><text>-</text></inputEntry>
        <outputEntry><text>false</text></outputEntry>
      </rule>
    </decisionTable>
  </decision>
</definitions>
"""


def _sample_rule(handle: str, version: int) -> Rule:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    return Rule(
        rule_id=new_rule_id(),
        rule_handle=handle,
        version=version,
        rule_group="g",
        salience=0,
        effective_from=t0,
        effective_to=None,
        is_active=True,
        rule_definition=RuleDefinition("r", RuleFormat.DRL),
        activation_group=None,
    )


def test_package_reexports_exist() -> None:
    assert compliance_pkg.Jurisdiction.US_ECOA_FCRA is not None
    assert callable(dmn_pkg.parse_dmn_decision_table_xml)
    assert callable(dmn_pkg.evaluate_dmn_decision_table_xml)
    assert callable(dmn_pkg.counterfactual_dmn_decision_table_xml)
    assert callable(compliance_pkg.adverse_action_record)
    assert callable(compliance_pkg.adverse_action_counterfactual_summary)
    assert integrations_pkg.FeastFeatureClient is not None
    assert integrations_pkg.TectonFeatureClient is not None
    assert callable(policy_pkg.query_opa)
    assert callable(policy_pkg.query_ranger_allowed)


def test_build_adverse_action_us_and_eu_stubs() -> None:
    ctx = AdverseActionContext(
        applicant_reference="acct-9",
        decision_date_iso="2026-01-15",
        primary_reason_codes=("D2",),
        creditor_or_controller_name="SparkBank",
    )
    us_txt = build_adverse_action_notice(ctx, Jurisdiction.US_ECOA_FCRA)
    assert "ECOA" in us_txt and "D2" in us_txt and "Template" in us_txt
    eu_txt = build_adverse_action_notice(ctx, Jurisdiction.EU_GDPR_ART22)
    assert "ARTICLE 22" in eu_txt and "Template" in eu_txt


def test_build_adverse_action_appendix_lines() -> None:
    ctx = AdverseActionContext(
        applicant_reference="a1",
        decision_date_iso="2026-01-01",
        primary_reason_codes=("X",),
        creditor_or_controller_name="C",
    )
    txt = build_adverse_action_notice(
        ctx,
        Jurisdiction.US_ECOA_FCRA,
        appendix_lines=("Contact: compliance@example.com",),
    )
    assert "compliance@example.com" in txt


_CF_DMN_FIRST = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="FIRST">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="tier"/>
<rule><inputEntry><text>100</text></inputEntry><outputEntry><text>"low"</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"high"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""


def test_counterfactual_dmn_decision_table_xml_differs_when_branch_changes() -> None:
    # DMN literal cells are compared as parsed strings; align env types with table literals.
    got = counterfactual_dmn_decision_table_xml(_CF_DMN_FIRST, {"k": "100"}, {"k": "200"})
    assert got["base"] == {"tier": "low"}
    assert got["counterfactual"] == {"tier": "high"}
    assert got["patch"] == {"k": "200"}
    assert got["outputs_differ"] is True


def test_counterfactual_dmn_decision_table_xml_same_when_patch_redundant() -> None:
    got = counterfactual_dmn_decision_table_xml(_CF_DMN_FIRST, {"k": "50"}, {"k": "50"})
    assert got["base"] == got["counterfactual"] == {"tier": "high"}
    assert got["outputs_differ"] is False


def test_evaluate_dmn_decision_table_xml_end_to_end() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn" id="ev"><decision><decisionTable>
<input><inputExpression><text>$.score</text></inputExpression></input>
<output name="tier"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"gold"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    out = evaluate_dmn_decision_table_xml(xml, {"score": 500})
    assert out == {"tier": "gold"}


def test_adverse_action_record_json_shape() -> None:
    ctx = AdverseActionContext("acct-z", "2026-02-02", ("RC1",), creditor_or_controller_name="Co")
    rec = adverse_action_record(ctx, Jurisdiction.EU_GDPR_ART22)
    assert rec["jurisdiction"] == "EU_GDPR_ART22"
    assert rec["reason_codes"] == ["RC1"] and "notice_text" in rec


def test_adverse_action_counterfactual_summary_reason_delta() -> None:
    base = AdverseActionContext("a1", "2026-03-01", ("X",), creditor_or_controller_name="C")
    alt = AdverseActionContext("a1", "2026-03-01", ("X", "Y"), creditor_or_controller_name="C")
    got = adverse_action_counterfactual_summary(base, alt, Jurisdiction.US_ECOA_FCRA)
    assert got["reason_codes_added"] == ["Y"] and got["reason_codes_removed"] == []
    assert got["notices_differ"] is True


def test_adverse_action_counterfactual_summary_identical() -> None:
    ctx = AdverseActionContext("b", "2026-01-01", ("Z",))
    got = adverse_action_counterfactual_summary(ctx, ctx, Jurisdiction.EU_GDPR_ART22)
    assert got["reason_codes_added"] == [] and got["reason_codes_removed"] == []
    assert got["notices_differ"] is False


def test_adverse_action_counterfactual_summary_codes_removed() -> None:
    base = AdverseActionContext("rm", "2026-04-01", ("X", "Y"))
    alt = AdverseActionContext("rm", "2026-04-01", ("X",))
    got = adverse_action_counterfactual_summary(base, alt, Jurisdiction.US_ECOA_FCRA)
    assert got["reason_codes_removed"] == ["Y"] and got["reason_codes_added"] == []


def test_parse_simple_dmn_table() -> None:
    dt = parse_dmn_decision_table_xml(_SIMPLE_DMN_XML)
    assert dt.name == "LoanDecision"
    assert len(dt.rows) == 2
    assert dt.hit_policy == HitPolicy.FIRST


_COLLECT_DMN = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="COLLECT">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="tag"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"a"</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"b"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""


def test_dmn_collect_hit_policy_returns_all_matching_rows() -> None:
    dt = parse_dmn_decision_table_xml(_COLLECT_DMN)
    assert dt.hit_policy == HitPolicy.COLLECT
    assert evaluate_dmn_decision_table_xml(_COLLECT_DMN, {"k": "x"}) == [{"tag": "a"}, {"tag": "b"}]


_PRIORITY_DMN = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="PRIORITY">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="tier"/>
<rule priority="3"><inputEntry><text>-</text></inputEntry><outputEntry><text>"low"</text></outputEntry></rule>
<rule priority="40"><inputEntry><text>-</text></inputEntry><outputEntry><text>"high"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""


def test_dmn_priority_hit_policy_and_rule_priority_attribute() -> None:
    dt = parse_dmn_decision_table_xml(_PRIORITY_DMN)
    assert dt.hit_policy == HitPolicy.PRIORITY
    assert [r.priority for r in dt.rows] == [3, 40]
    assert evaluate_dmn_decision_table_xml(_PRIORITY_DMN, {"k": "1"}) == {"tier": "high"}


def test_dmn_rule_priority_invalid_attribute_defaults_to_zero() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="PRIORITY">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="o"/>
<rule priority="oops"><inputEntry><text>-</text></inputEntry><outputEntry><text>"x"</text></outputEntry></rule>
<rule priority="7"><inputEntry><text>-</text></inputEntry><outputEntry><text>"y"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    dt = parse_dmn_decision_table_xml(xml)
    assert [r.priority for r in dt.rows] == [0, 7]
    assert evaluate_dmn_decision_table_xml(xml, {"k": "z"}) == {"o": "y"}


def test_dmn_hit_policy_unique_label_explicit() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="UNIQUE">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="o"/>
<rule><inputEntry><text>1</text></inputEntry><outputEntry><text>"a"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    assert parse_dmn_decision_table_xml(xml).hit_policy == HitPolicy.UNIQUE


def test_dmn_rule_order_hit_policy_maps_to_first() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="RULE ORDER">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="o"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"first"</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"second"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    dt = parse_dmn_decision_table_xml(xml)
    assert dt.hit_policy == HitPolicy.FIRST
    assert evaluate_dmn_decision_table_xml(xml, {"k": "x"}) == {"o": "first"}


def test_dmn_any_hit_policy_maps_to_collect() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="ANY">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="tag"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"a"</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"b"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    assert parse_dmn_decision_table_xml(xml).hit_policy == HitPolicy.COLLECT
    assert evaluate_dmn_decision_table_xml(xml, {"k": "1"}) == [{"tag": "a"}, {"tag": "b"}]


def test_dmn_output_order_hit_policy_maps_to_collect() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="OUTPUT ORDER">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="tag"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"a"</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"b"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    assert parse_dmn_decision_table_xml(xml).hit_policy == HitPolicy.COLLECT
    assert evaluate_dmn_decision_table_xml(xml, {"k": "1"}) == [{"tag": "a"}, {"tag": "b"}]


def test_dmn_output_first_hit_policy_maps_to_first() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="OUTPUT FIRST">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="o"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"p"</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"q"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    assert parse_dmn_decision_table_xml(xml).hit_policy == HitPolicy.FIRST
    assert evaluate_dmn_decision_table_xml(xml, {"k": "z"}) == {"o": "p"}


def test_dmn_output_priority_hit_policy_maps_to_priority() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="OUTPUT PRIORITY">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="o"/>
<rule priority="1"><inputEntry><text>-</text></inputEntry><outputEntry><text>"low"</text></outputEntry></rule>
<rule priority="50"><inputEntry><text>-</text></inputEntry><outputEntry><text>"high"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    assert parse_dmn_decision_table_xml(xml).hit_policy == HitPolicy.PRIORITY
    assert evaluate_dmn_decision_table_xml(xml, {"k": "9"}) == {"o": "high"}


_COLLECT_SUM_DMN = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="COLLECT SUM">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="total"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>10</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>20</text></outputEntry></rule>
</decisionTable></decision></definitions>"""


def test_dmn_collect_sum_hit_policy_parses_and_evaluates() -> None:
    dt = parse_dmn_decision_table_xml(_COLLECT_SUM_DMN)
    assert dt.hit_policy == HitPolicy.COLLECT_SUM
    assert evaluate_dmn_decision_table_xml(_COLLECT_SUM_DMN, {"k": "x"}) == {"total": 30}


def test_dmn_collect_count_min_max_hit_policies() -> None:
    base = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="{hp}">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="v"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>3</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>9</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    assert evaluate_dmn_decision_table_xml(base.format(hp="COLLECT COUNT"), {"k": "1"}) == {"v": 2}
    assert evaluate_dmn_decision_table_xml(base.format(hp="COLLECT MIN"), {"k": "1"}) == {"v": 3}
    assert evaluate_dmn_decision_table_xml(base.format(hp="COLLECT MAX"), {"k": "1"}) == {"v": 9}


def test_dmn_unknown_hit_policy_label_defaults_to_unique() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="NO_SUCH_POLICY">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="o"/>
<rule><inputEntry><text>1</text></inputEntry><outputEntry><text>"a"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    assert parse_dmn_decision_table_xml(xml).hit_policy == HitPolicy.UNIQUE


def test_dmn_parse_errors_and_two_tables() -> None:
    with pytest.raises(DmnParseError, match="exactly one decisionTable"):
        parse_dmn_decision_table_xml('<definitions xmlns="x"/>')
    with pytest.raises(DmnParseError):
        parse_dmn_decision_table_xml("<<<")
    xml_two = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn">
 <decision id="x"><decisionTable id="a">
   <input id="i"><inputExpression><text>$.z</text></inputExpression></input>
   <output id="o" name="out"/>
   <rule id="r"><inputEntry><text>-</text></inputEntry><outputEntry><text>x</text></outputEntry></rule>
 </decisionTable><decisionTable id="b">
   <input id="j"><inputExpression><text>$.z</text></inputExpression></input>
   <output id="p" name="o2"/>
   <rule><inputEntry><text>-</text></inputEntry><outputEntry><text>y</text></outputEntry></rule>
 </decisionTable></decision></definitions>"""
    with pytest.raises(DmnParseError):
        parse_dmn_decision_table_xml(xml_two)


def test_feast_helpers_and_online_feature_branches() -> None:
    merged: dict[str, object] = {"t": {}}
    merge_features_into_fact(merged, {"some-score": 1}, prefix="f_")
    assert merged["f_some_score"] == 1

    assert feast_fetch_row(None, features=["x"], entity_id_field="id", entity_id="1") == {}

    mock_store = MagicMock()

    class _FV:
        def to_dict(self) -> dict[str, object]:
            return {"f_col": [9]}

    mock_store.get_online_features.return_value = _FV()
    cli = FeastFeatureClient(repo_path="/tmp/repo", _store=mock_store)
    assert cli.get_online_features(features=("f:v1",), entity_rows=[{"e": "1"}])["f_col"] == [9]
    row = feast_fetch_row(cli, features=["f:v1"], entity_id_field="e", entity_id="1")
    assert row["f_col"] == 9

    class _Df:
        def to_dict(self, orient: str | None = None) -> dict[str, list[int]]:
            return {"z_col": [3]}

    class _FvNoDict:
        def to_df(self) -> _Df:
            return _Df()

    mock_store.get_online_features.return_value = _FvNoDict()
    cli2 = FeastFeatureClient(repo_path="/x", _store=mock_store)
    assert cli2.get_online_features(features=["z"], entity_rows=[{"e": 1}]) == {"z_col": [3]}

    mock_store.get_online_features.return_value = {"bare": ["v"]}
    assert cli.get_online_features(features=["bare"], entity_rows=[{}]) == {"bare": ["v"]}

    missing_repo = FeastFeatureClient(repo_path=None, _store=None)
    with pytest.raises(ValueError, match="repo_path"):
        missing_repo.get_online_features(features=[], entity_rows=[])

    no_feast_wheel = FeastFeatureClient(repo_path="/tmp/feast_repo_xyz", _store=None)
    real_import = builtins.__import__

    def _block_feast(name: str, /, *args: object, **kwargs: object) -> object:
        if name == "feast":
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    with patch.object(builtins, "__import__", _block_feast):
        with pytest.raises(RuntimeError, match="feast"):
            no_feast_wheel.get_online_features(features=[], entity_rows=[])


def test_ranger_stub() -> None:
    assert ranger_allow_stub(user=" ", resource_type="t", resource_name="r", action="read") is False
    assert (
        ranger_allow_stub(user="alice", resource_type="*", resource_name="x", action="rw") is True
    )


def test_query_opa_via_httpx_mocks() -> None:
    ok = MagicMock(status_code=200, text='{"result":{"allow":true}}')
    ok.json.return_value = {"result": {"allow": True}}

    bad_status = MagicMock(status_code=502, text="bad")
    bad_json = MagicMock(status_code=200, text="{")
    bad_json.json.side_effect = json.JSONDecodeError("doc", "{", 0)
    weird_result = MagicMock(status_code=200, text='{"result":"x"}')
    weird_result.json.return_value = {"result": "scalar"}

    with patch.object(httpx, "post") as hp:
        hp.side_effect = [ok]
        got = query_opa("http://localhost:8181/", package_path="app.allow", input_data={"u": "a"})
        assert got == {"allow": True}

        hp.side_effect = [bad_status]
        with pytest.raises(OpaDecisionError, match="502"):
            query_opa("http://opa/", package_path="a.b", input_data={})

        hp.side_effect = [bad_json]
        with pytest.raises(OpaDecisionError, match="not JSON"):
            query_opa("http://opa/", package_path="c.d", input_data={})

        hp.side_effect = [weird_result]
        with pytest.raises(OpaDecisionError, match="not an object"):
            query_opa("http://opa/", package_path="c.d", input_data={})

        hp.side_effect = [OSError("no route")]
        with pytest.raises(OpaDecisionError, match="no route"):
            query_opa("http://opa/", package_path="c.d", input_data={})


def test_iceberg_hydrating_optional_sink_roundtrip() -> None:
    snapshots: list[tuple[int, str]] = []

    def sink(_blob: str, handle: str, version: int) -> None:
        snapshots.append((version, handle))

    store = IcebergHydratingRuleStore(version_sink=sink)
    base = _sample_rule("h-sink", 1)
    store.insert(base)
    assert snapshots == [(1, "h-sink")]

    no_sink = IcebergHydratingRuleStore(version_sink=None)
    alt = base.with_updates(rule_id=new_rule_id(), rule_handle="other", version=1)
    no_sink.insert(alt)


def test_create_rule_store_iceberg_callbacks() -> None:
    versions: list[int] = []

    def sink(_blob: str, _handle: str, version: int) -> None:
        versions.append(version)

    store = create_rule_store("iceberg", iceberg_version_sink=sink)
    dup = _sample_rule("ice-handle", 1)
    first = store.insert(dup)
    assert versions == [1]
    store.update("ice-handle", first.with_updates(salience=77))
    assert versions == [1, 1]


def test_feast_resolve_loads_stub_feature_store_module() -> None:
    feast_mod = types.ModuleType("feast")

    ms = MagicMock()

    class _Fv:
        def to_dict(self) -> dict[str, list[str]]:
            return {"col_empty": [], "col_one": ["v"]}

    ms.get_online_features.return_value = _Fv()
    feast_mod.FeatureStore = MagicMock(return_value=ms)

    with patch.dict("sys.modules", {"feast": feast_mod}):
        cli = FeastFeatureClient(repo_path="/feast/repo", _store=None)
        out = cli.get_online_features(features=["f"], entity_rows=[{"id": "1"}])
        assert out["col_empty"] == []
        feast_mod.FeatureStore.assert_called_once_with(repo_path="/feast/repo")
    row = feast_fetch_row(
        cli, features=["col_empty", "col_one"], entity_id_field="e", entity_id="x"
    )
    assert row["col_empty"] == [] and row["col_one"] == "v"


def test_dmn_hit_unique_fallback_name_and_helpers() -> None:
    xml = """<?xml version="1.0"?>
<definitions xmlns="https://camunda.org/schema/1.0/dmn" id="FromRootOnly">
 <decision id="zz">
  <decisionTable id="tbl">
   <input id="i_plain"/>
   <input><inputExpression><text>broken</text></inputExpression></input>
   <output id="onlyid"/>
   <rule>
    <inputEntry/>
    <inputEntry><text>3.14</text></inputEntry>
    <outputEntry><text>NA</text></outputEntry>
   </rule>
   <rule>
    <inputEntry><text>false</text></inputEntry>
    <inputEntry><text>700</text></inputEntry>
    <outputEntry><text>"lbl"</text></outputEntry>
   </rule>
  </decisionTable>
 </decision>
</definitions>"""
    dt = parse_dmn_decision_table_xml(xml)
    assert dt.name == "FromRootOnly"
    assert dt.hit_policy == HitPolicy.UNIQUE


def test_guess_cell_type_bool_and_field_expression_break_branch() -> None:
    tbl = """<?xml version="1.0"?>
<definitions xmlns="z" id="boolcase"><decision><decisionTable>
<input/><output/><rule><inputEntry><text>true</text></inputEntry>
<outputEntry><text>1</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    dt_bool = parse_dmn_decision_table_xml(tbl)
    assert dt_bool.input_columns[0].col_type.value == "BOOL"

    tbl_brk = """<?xml version="1.0"?>
<definitions xmlns="z" id="brk"><decision><decisionTable>
<input><inputExpression><empty/><empty/></inputExpression></input>
<input/><output/><rule><inputEntry><text>1</text></inputEntry>
<inputEntry><text>2</text></inputEntry><outputEntry><text>-</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    dt_break = parse_dmn_decision_table_xml(tbl_brk)
    assert dt_break.input_columns[0].field_ref == "input"


def test_dmn_parse_additional_errors() -> None:
    no_out = """<?xml version="1.0"?>
<definitions xmlns="x"><decision><decisionTable><input/><rule><inputEntry><text>a</text></inputEntry></rule></decisionTable></decision></definitions>"""
    with pytest.raises(DmnParseError, match="input and output"):
        parse_dmn_decision_table_xml(no_out)

    no_rules = """<?xml version="1.0"?>
<definitions xmlns="x"><decision><decisionTable hitPolicy="UNIQUE">
<input/><output name="x"/></decisionTable></decision></definitions>"""
    with pytest.raises(DmnParseError, match="no rules"):
        parse_dmn_decision_table_xml(no_rules)

    bad_cells = """<?xml version="1.0"?>
<definitions xmlns="x"><decision><decisionTable><input/><output/><rule><outputEntry><text>z</text></outputEntry></rule></decisionTable></decision></definitions>"""
    with pytest.raises(DmnParseError, match="cell count"):
        parse_dmn_decision_table_xml(bad_cells)

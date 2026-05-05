"""Cover ``sparkrules.native.executor`` with a mocked ``sparkrules_native`` module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import sparkrules.native.executor as native_exec_mod
from sparkrules.compiler.rulepack import RulePack
from sparkrules.executor.local_executor import LocalRuleExecutor

from sparkrules.native.executor import NativeRuleExecutor, score_result_from_native_dict


def _json_row_for_pack(pack: RulePack, fact: dict) -> str:
    ref = LocalRuleExecutor.from_rulepack(pack).score(fact)
    return json.dumps(
        {
            "fires": [
                {
                    "rule_name": f.rule_name,
                    "salience": f.salience,
                    "fired": f.fired,
                    "action_output": dict(f.action_output),
                    "reason_codes": list(f.reason_codes),
                }
                for f in ref.fires
            ],
            "fired_any": ref.fired_any,
            "merged_actions": dict(ref.merged_actions),
        },
        separators=(",", ":"),
    )


def test_native_executor_score_with_mock() -> None:
    drl = "rule rr when $t : T ( $t.x >= 2 ) then result.ok = true; end"
    pack = RulePack.from_drl(drl)
    compiled = object()
    native_mod = MagicMock()
    native_mod.compile_rulepack.return_value = compiled
    row_json = _json_row_for_pack(pack, {"t": {"x": 3}})
    native_mod.score_rows.return_value = [row_json]

    with patch.object(native_exec_mod, "load_native", return_value=native_mod):
        ex = NativeRuleExecutor.from_rulepack(pack)
        out = ex.score({"t": {"x": 3}})

    assert ex._compiled is compiled
    assert out.fired_any is True
    native_mod.score_rows.assert_called_once_with(
        compiled,
        [json.dumps({"t": {"x": 3}}, separators=(",", ":"), default=str)],
    )


def test_native_executor_apply_many_mocked() -> None:
    drl = "rule r when $t : T ( true ) then result.v = $t.a; end"
    pack = RulePack.from_drl(drl)
    native_mod = MagicMock()
    native_mod.compile_rulepack.return_value = "C"
    facts = [{"t": {"a": 1}}, {"t": {"a": 2}}]
    native_mod.score_rows.return_value = [_json_row_for_pack(pack, z) for z in facts]

    with patch.object(native_exec_mod, "load_native", return_value=native_mod):
        exe = NativeRuleExecutor.from_rulepack(pack)
        got = exe.apply(facts)

    assert len(got) == 2


def test_native_executor_from_drl_with_mock() -> None:
    native_mod = MagicMock()
    native_mod.compile_rulepack.return_value = "XC"
    drl = "rule fd when $t : T ( true ) then end"
    with patch.object(native_exec_mod, "load_native", return_value=native_mod):
        ex = NativeRuleExecutor.from_drl(drl)
    assert ex._compiled == "XC"
    assert ex.rulepack.rules[0].name == "fd"
    native_mod.compile_rulepack.assert_called_once()


def test_score_result_from_native_dict_matches_roundtrip_json() -> None:
    pack = RulePack.from_drl("rule q when $t : T ( true ) then end")
    d = json.loads(_json_row_for_pack(pack, {"t": {}}))
    sr = score_result_from_native_dict(d)
    loc = LocalRuleExecutor.from_rulepack(pack).score({"t": {}})
    assert sr.fires == loc.fires
    assert sr.merged_actions == loc.merged_actions

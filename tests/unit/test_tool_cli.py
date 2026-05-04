from __future__ import annotations

import argparse
import json
from pathlib import Path
import runpy

import pytest

from sparkrules.tools import cli

_DRL = "rule r when $t : T ( true ) then result.ok = true; end"


def test_cli_without_command_returns_1(capsys) -> None:
    rc = cli.main([])
    assert rc == 1
    assert "usage:" in capsys.readouterr().out


def test_cli_health(capsys) -> None:
    assert cli.main(["health"]) == 0
    out = capsys.readouterr().out.strip()
    assert json.loads(out) == {"status": "ok"}


def test_cli_validate_ok_and_error(capsys) -> None:
    assert cli.main(["validate", "--drl", _DRL]) == 0
    assert capsys.readouterr().out.strip() == "ok"
    assert cli.main(["validate", "--drl", "not drl"]) == 2
    assert "validate failed" in capsys.readouterr().err


def test_cli_validate_file(tmp_path: Path, capsys) -> None:
    p = tmp_path / "rule.drl"
    p.write_text(_DRL, encoding="utf-8")
    assert cli.main(["validate", "--file", str(p)]) == 0
    assert capsys.readouterr().out.strip() == "ok"


def test_cli_simulate_ok(capsys) -> None:
    rc = cli.main(["simulate", "--drl", _DRL, "--fact-json", '{"t": {"x": 1}}'])
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["fired"] is True
    assert out["action"].get("ok") is True


def test_cli_simulate_bad_fact_and_bad_drl(capsys) -> None:
    assert cli.main(["simulate", "--drl", _DRL, "--fact-json", "[]"]) == 2
    assert "invalid fact-json" in capsys.readouterr().err
    assert cli.main(["simulate", "--drl", "not drl", "--fact-json", "{}"]) == 2
    assert "simulate failed" in capsys.readouterr().err


_CHAIN_DRL = """rule a when $t : T ( true ) then result.n = 1; end
rule b when $t : T ( true ) then result.n = 2; end"""


def test_cli_simulate_chain_ok_and_json_errors(capsys) -> None:
    rc = cli.main(
        [
            "simulate-chain",
            "--drl",
            _CHAIN_DRL,
            "--fact-json",
            '{"t":{}}',
            "--stop-on-decline",
            "--agenda-group-modes-json",
            "{}",
        ],
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["any_fired"] is True
    assert len(out["steps"]) == 2
    assert cli.main(["simulate-chain", "--drl", _DRL, "--fact-json", "[]"]) == 2
    assert "invalid json" in capsys.readouterr().err
    assert (
        cli.main(
            [
                "simulate-chain",
                "--drl",
                _DRL,
                "--fact-json",
                "{}",
                "--agenda-group-modes-json",
                "[]",
            ],
        )
        == 2
    )
    assert "invalid json" in capsys.readouterr().err
    assert (
        cli.main(
            [
                "simulate-chain",
                "--drl",
                _DRL,
                "--fact-json",
                "{}",
                "--agenda-group-modes-json",
                '{"g": 1}',
            ],
        )
        == 2
    )
    assert "agenda group modes must" in capsys.readouterr().err
    assert cli.main(["simulate-chain", "--drl", "not drl", "--fact-json", "{}"]) == 2
    assert "simulate-chain failed" in capsys.readouterr().err


def test_cli_simulate_chain_file(tmp_path: Path, capsys) -> None:
    p = tmp_path / "c.drl"
    p.write_text(_CHAIN_DRL, encoding="utf-8")
    assert cli.main(["simulate-chain", "--file", str(p), "--fact-json", '{"t":{}}']) == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["any_fired"] is True


def test_cli_simulate_shadow_ok_and_errors(tmp_path: Path, capsys) -> None:
    p1 = tmp_path / "p.drl"
    p1.write_text('rule p when $t : T ( true ) then result.d = "p"; end', encoding="utf-8")
    assert (
        cli.main(
            [
                "simulate-shadow",
                "--primary-file",
                str(p1),
                "--shadow-drl",
                'rule s when $t : T ( true ) then result.d = "s"; end',
                "--fact-json",
                '{"t":{}}',
                "--run-id",
                "r99",
            ],
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out.strip())
    assert out["drifted"] is True and out["run_id"] == "r99"
    assert (
        cli.main(
            [
                "simulate-shadow",
                "--primary-drl",
                _DRL,
                "--shadow-drl",
                _DRL,
                "--fact-json",
                "null",
            ],
        )
        == 2
    )
    assert "invalid fact-json" in capsys.readouterr().err
    assert (
        cli.main(
            [
                "simulate-shadow",
                "--primary-drl",
                "bad",
                "--shadow-drl",
                _DRL,
                "--fact-json",
                "{}",
            ],
        )
        == 2
    )
    assert "simulate-shadow failed" in capsys.readouterr().err


def test_cli_simulate_coverage_ok_and_errors(capsys) -> None:
    facts = '[{"t":{"x":1}},{"t":{"x":0}}]'
    rc = cli.main(
        [
            "simulate-coverage",
            "--drl",
            """rule r1 when $t : T ( $t.x == 1 ) then result.a = true; end
rule r2 when $t : T ( $t.x == 0 ) then result.b = true; end""",
            "--facts-json",
            facts,
        ],
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["total_facts"] == 2 and out["covered_rules"] == 2
    by = {i["rule_name"]: i for i in out["items"]}
    assert by["r1"]["fired_count"] == 1 and by["r2"]["fired_count"] == 1
    assert cli.main(["simulate-coverage", "--drl", _DRL, "--facts-json", "{}"]) == 2
    assert "invalid facts-json" in capsys.readouterr().err
    assert cli.main(["simulate-coverage", "--drl", _DRL, "--facts-json", "[1]"]) == 2
    assert "invalid facts-json" in capsys.readouterr().err
    assert cli.main(["simulate-coverage", "--drl", "bad", "--facts-json", "[{}]"]) == 2
    assert "simulate-coverage failed" in capsys.readouterr().err


def test_cli_chaos_check_ok_and_fail(capsys) -> None:
    assert cli.main(["chaos-check", "--max-retries", "1"]) == 0
    ok = json.loads(capsys.readouterr().out.strip())
    assert ok["ok"] is True
    assert ok["attempts"] == 1
    assert cli.main(["chaos-check", "--fail-attempts", "1", "--max-retries", "0"]) == 2
    bad = json.loads(capsys.readouterr().out.strip())
    assert bad["ok"] is False
    assert bad["injected_failures"] == 1


def test_cli_lsp_check(capsys) -> None:
    assert cli.main(["lsp-check", "--drl", _DRL, "--prefix", "ru"]) == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["diagnostics"] == []
    assert "rule" in out["completions"]
    assert cli.main(["lsp-check", "--drl", "bad drl"]) == 0
    out_bad = json.loads(capsys.readouterr().out.strip())
    assert out_bad["diagnostics"]


_MINI_DMN_CLI = """<?xml version="1.0"?><definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision>
<decisionTable><input><inputExpression><text>$.k</text></inputExpression></input>
<output name="out"/><rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"ok"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""


def test_cli_dmn_evaluate_xml_and_file(tmp_path: Path, capsys) -> None:
    rc = cli.main(
        ["dmn-evaluate", "--xml", _MINI_DMN_CLI, "--env-json", '{"k": "z"}'],
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["result"] == {"out": "ok"}
    p = tmp_path / "m.dmn"
    p.write_text(_MINI_DMN_CLI, encoding="utf-8")
    assert cli.main(["dmn-evaluate", "--file", str(p), "--env-json", "{}"]) == 0
    out2 = json.loads(capsys.readouterr().out.strip())
    assert out2["result"] == {"out": "ok"}


def test_cli_dmn_evaluate_bad_env_and_parse(capsys) -> None:
    assert cli.main(["dmn-evaluate", "--xml", _MINI_DMN_CLI, "--env-json", "[]"]) == 2
    assert "invalid env-json" in capsys.readouterr().err
    assert cli.main(["dmn-evaluate", "--xml", "<<<", "--env-json", "{}"]) == 2
    assert "dmn parse error" in capsys.readouterr().err


def test_cli_dmn_evaluate_unique_overlap(capsys) -> None:
    xml = """<?xml version="1.0"?><definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="UNIQUE">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="o"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>1</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>2</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    assert cli.main(["dmn-evaluate", "--xml", xml, "--env-json", '{"k":"x"}']) == 2
    assert "dmn evaluate error" in capsys.readouterr().err


def test_cli_dmn_evaluate_unexpected_error(capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a: object, **_k: object) -> object:
        raise KeyError("x")

    monkeypatch.setattr("sparkrules.tools.cli.evaluate_dmn_decision_table_xml", _boom)
    assert cli.main(["dmn-evaluate", "--xml", _MINI_DMN_CLI, "--env-json", "{}"]) == 2
    assert "dmn evaluate failed" in capsys.readouterr().err


def test_cli_dmn_counterfactual_parse_and_unexpected_error(
    capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (
        cli.main(
            ["dmn-counterfactual", "--xml", "<<<", "--base-env-json", "{}", "--patch-json", "{}"]
        )
        == 2
    )
    assert "dmn parse error" in capsys.readouterr().err

    def _boom(*_a: object, **_k: object) -> object:
        raise RuntimeError("x")

    monkeypatch.setattr("sparkrules.tools.cli.counterfactual_dmn_decision_table_xml", _boom)
    assert (
        cli.main(
            [
                "dmn-counterfactual",
                "--xml",
                _MINI_DMN_CLI,
                "--base-env-json",
                "{}",
                "--patch-json",
                "{}",
            ],
        )
        == 2
    )
    assert "dmn counterfactual failed" in capsys.readouterr().err


def test_cli_dmn_counterfactual_aggregate_error(capsys) -> None:
    xml = """<?xml version="1.0"?><definitions xmlns="https://camunda.org/schema/1.0/dmn"><decision><decisionTable hitPolicy="COLLECT SUM">
<input><inputExpression><text>$.k</text></inputExpression></input>
<output name="o"/>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>1</text></outputEntry></rule>
<rule><inputEntry><text>-</text></inputEntry><outputEntry><text>"x"</text></outputEntry></rule>
</decisionTable></decision></definitions>"""
    assert (
        cli.main(
            [
                "dmn-counterfactual",
                "--xml",
                xml,
                "--base-env-json",
                '{"k":"1"}',
                "--patch-json",
                "{}",
            ],
        )
        == 2
    )
    assert "dmn counterfactual error" in capsys.readouterr().err


def test_cli_dmn_counterfactual_ok_and_bad_json(capsys) -> None:
    assert (
        cli.main(
            [
                "dmn-counterfactual",
                "--xml",
                _MINI_DMN_CLI,
                "--base-env-json",
                '{"k": "1"}',
                "--patch-json",
                '{"k": "2"}',
            ],
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out.strip())
    assert out["outputs_differ"] is False
    assert (
        cli.main(
            [
                "dmn-counterfactual",
                "--xml",
                _MINI_DMN_CLI,
                "--base-env-json",
                "[]",
                "--patch-json",
                "{}",
            ]
        )
        == 2
    )
    assert "invalid json" in capsys.readouterr().err


def test_cli_counterfactual_check(capsys) -> None:
    drl = 'rule r when $t : T ( $t.x > 10 ) then result.decision = "decline"; end'
    assert (
        cli.main(
            [
                "counterfactual-check",
                "--drl",
                drl,
                "--baseline-fact-json",
                '{"t": {"x": 1}}',
                "--candidate-fact-json",
                '{"t": {"x": 20}}',
            ]
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out.strip())
    assert out["drifted"] is True
    assert "decision" in out["drift_fields"]
    assert (
        cli.main(
            [
                "counterfactual-check",
                "--drl",
                drl,
                "--baseline-fact-json",
                "[]",
                "--candidate-fact-json",
                "{}",
            ]
        )
        == 2
    )
    assert "invalid fact-json" in capsys.readouterr().err
    assert (
        cli.main(
            [
                "counterfactual-check",
                "--drl",
                "bad drl",
                "--baseline-fact-json",
                "{}",
                "--candidate-fact-json",
                "{}",
            ]
        )
        == 2
    )
    assert "counterfactual failed" in capsys.readouterr().err


def test_cli_unknown_command_fallback(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    def _fake_parse_args(self, argv):  # noqa: ANN001
        return argparse.Namespace(command="unknown")

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", _fake_parse_args)
    assert cli.main(["ignored"]) == 1
    assert "usage:" in capsys.readouterr().out


def test_cli_runpy_as_main(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["sre-cli"])
    try:
        runpy.run_module("sparkrules.tools.cli", run_name="__main__")
    except SystemExit as e:
        assert e.code == 1


def test_cli_cost_and_stream_kafka_iceberg(capsys) -> None:
    assert cli.main(["cost", "--rows", "1000", "--rules", "10", "--cluster", "glue"]) == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["cluster"] == "glue"
    assert "estimate_usd" in out
    assert cli.main(["stream-kafka-iceberg", "--topic", "t1", "--dry-run"]) == 0
    stream_out = json.loads(capsys.readouterr().out.strip())
    assert stream_out["dry_run"] is True
    assert stream_out["plan"]["source"]["topic"] == "t1"

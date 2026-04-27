from __future__ import annotations

import argparse
import json
from pathlib import Path
import runpy

import pytest

from sre.tools import cli

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


def test_cli_chaos_check_ok_and_fail(capsys) -> None:
    assert cli.main(["chaos-check", "--max-retries", "1"]) == 0
    ok = json.loads(capsys.readouterr().out.strip())
    assert ok["ok"] is True
    assert ok["attempts"] == 1
    assert cli.main(["chaos-check", "--fail-attempts", "1", "--max-retries", "0"]) == 2
    bad = json.loads(capsys.readouterr().out.strip())
    assert bad["ok"] is False
    assert bad["injected_failures"] == 1


def test_cli_unknown_command_fallback(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    def _fake_parse_args(self, argv):  # noqa: ANN001
        return argparse.Namespace(command="unknown")

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", _fake_parse_args)
    assert cli.main(["ignored"]) == 1
    assert "usage:" in capsys.readouterr().out


def test_cli_runpy_as_main(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["sre-cli"])
    try:
        runpy.run_module("sre.tools.cli", run_name="__main__")
    except SystemExit as e:
        assert e.code == 1

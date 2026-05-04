from __future__ import annotations

import json
import runpy
import sys

import pytest

from sparkrules.tools import stream_kafka_iceberg


def test_stream_stub_main_default(capsys) -> None:
    assert stream_kafka_iceberg.main([]) == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["plan"]["source"]["kind"] == "kafka"
    assert out["dry_run"] is False


def test_stream_stub_main_dry_run(capsys) -> None:
    assert stream_kafka_iceberg.main(["--dry-run"]) == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["dry_run"] is True


def test_stream_stub_runpy_main(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["stream_kafka_iceberg", "--dry-run"])
    with pytest.raises(SystemExit) as ei:
        runpy.run_module("sparkrules.tools.stream_kafka_iceberg", run_name="__main__")
    assert ei.value.code == 0

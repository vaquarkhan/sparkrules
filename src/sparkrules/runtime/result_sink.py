from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SinkWriteResult:
    format: str
    snapshot_id: str


class ResultSink:
    def write(self, rows: list[dict[str, Any]]) -> SinkWriteResult:
        raise NotImplementedError


@dataclass
class _FileSink(ResultSink):
    fmt: str
    path: Path

    def write(self, rows: list[dict[str, Any]]) -> SinkWriteResult:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(rows, sort_keys=True)
        self.path.write_text(body, encoding="utf-8")
        if self.fmt == "parquet":
            sid = hashlib.sha256(f"{self.path.name}:{self.path.stat().st_size}".encode()).hexdigest()
        else:
            sid = hashlib.sha256(body.encode()).hexdigest()
        return SinkWriteResult(format=self.fmt, snapshot_id=sid)


def create_result_sink(fmt: str, out_dir: str = "out") -> ResultSink:
    f = fmt.lower()
    if f not in {"iceberg", "delta", "hudi", "parquet"}:
        raise ValueError(f"unknown result sink format: {fmt!r}")
    return _FileSink(fmt=f, path=Path(out_dir) / f"results.{f}.json")

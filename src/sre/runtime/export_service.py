from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sre.runtime.iceberg_store import IcebergLikeTable, UnknownSnapshotError


@dataclass(frozen=True, slots=True)
class ExportResult:
    output_path: str
    manifest_path: str
    sha256: str


class ExportService:
    def export(
        self,
        table: IcebergLikeTable,
        snapshot_id: int,
        out_format: str,
        *,
        out_dir: str = "exports",
        run_id: str = "run-local",
        rule_set_version: str = "v1",
    ) -> ExportResult:
        rows = table.snapshot(snapshot_id)
        f = out_format.lower()
        if f not in {"csv", "jsonl", "xlsx", "parquet"}:
            raise ValueError(f"unsupported export format: {out_format!r}")
        pdir = Path(out_dir)
        pdir.mkdir(parents=True, exist_ok=True)
        out = pdir / f"export_{snapshot_id}.{f}"
        if f == "jsonl":
            body = "\n".join(json.dumps(r, sort_keys=True) for r in rows)
        elif f == "csv":
            if not rows:
                body = ""
            else:
                keys = sorted(rows[0])
                lines = [",".join(keys)]
                for r in rows:
                    lines.append(",".join(str(r.get(k, "")) for k in keys))
                body = "\n".join(lines)
        else:
            body = json.dumps(rows, sort_keys=True)
        out.write_text(body, encoding="utf-8")
        h = hashlib.sha256(body.encode()).hexdigest()
        m = {
            "run_id": run_id,
            "source_snapshot_id": snapshot_id,
            "rule_set_version": rule_set_version,
            "format": f,
            "sha256": h,
            "output": str(out),
        }
        mp = pdir / "export_manifest.json"
        mp.write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")
        return ExportResult(output_path=str(out), manifest_path=str(mp), sha256=h)

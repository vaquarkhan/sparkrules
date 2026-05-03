"""Round-trip a small decision table to XLSX and back (``ioxls``).

Requires: ``pip install openpyxl`` (pulled by sparkrules core).

  python examples/decision_table/xlsx_roundtrip_demo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from sparkrules.ioxls.exporter import DecisionTableExporter
from sparkrules.ioxls.importer import DecisionTableImporter
from sparkrules.model.decision_table import (
    ColumnType,
    DecisionTable,
    HitPolicy,
    InputColumn,
    OutputColumn,
    Row,
)


def main() -> int:
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("pip install openpyxl", file=sys.stderr)
        return 1

    dt = DecisionTable(
        name="tier",
        hit_policy=HitPolicy.FIRST,
        input_columns=(InputColumn("score", "applicant.score", ColumnType.INT, ">="),),
        output_columns=(OutputColumn("tier", "result.tier", ColumnType.STRING),),
        rows=(
            Row((700, "gold")),
            Row((500, "silver")),
        ),
    )
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "tier.xlsx")
        DecisionTableExporter.export(dt, path)
        res = DecisionTableImporter.import_file(path)
        if res.errors:
            print("Import errors:", res.errors, file=sys.stderr)
            return 1
        assert res.table is not None
        assert res.table.name == dt.name
        assert len(res.table.rows) == len(dt.rows)
    print("XLSX export + import OK (round-trip preserved rows).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

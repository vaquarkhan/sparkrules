import sys
from pathlib import Path

import pytest

from sparkrules.tools import smoke_drl


def test_smoke_main_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["smoke"])
    assert smoke_drl.main() == 0


def test_smoke_main_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "r.drl"
    p.write_text(
        "rule z when $t : T (1==1) then end\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["smoke", str(p)])
    assert smoke_drl.main() == 0

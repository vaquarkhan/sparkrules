"""Evaluate a RulePack on a pandas DataFrame (V2 ``apply_pandas`` path).

Requires: ``pip install pandas`` (included in ``sparkrules[test]`` dev install).

  python examples/python/apply_pandas_demo.py
"""

from __future__ import annotations

import sys

try:
    import pandas as pd
except ImportError:
    print("pip install pandas", file=sys.stderr)
    raise SystemExit(1) from None

from sparkrules.compiler.rulepack import RulePack
from sparkrules.executor.pandas_executor import apply_pandas

DRL = """
rule "high" salience 10 when $t : T ( $t.amount > 100 ) then result.tier = "gold"; end
rule "low" salience 5 when $t : T ( $t.amount <= 100 ) then result.tier = "standard"; end
"""


def main() -> int:
    pack = RulePack.from_drl(DRL)
    df = pd.DataFrame(
        [
            {"t": {"amount": 150}},
            {"t": {"amount": 40}},
        ]
    )
    out = apply_pandas(pack, df)
    print(out.to_string())
    assert "r_high" in out.columns and "action_tier" in out.columns
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

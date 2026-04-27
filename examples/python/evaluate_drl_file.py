"""Load a DRL file and evaluate it against a small hard-coded fact (example script).

The default environment includes both ``t`` and ``txn`` so ``examples/drl/minimal.drl``
and ``examples/drl/discount_tier.drl`` work; trim or change ``_DEFAULT_FACTS``
for your own rules.

  python examples/python/evaluate_drl_file.py examples/drl/minimal.drl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sre.compiler import evaluate_rule
from sre.parser import parse

# Example facts: use the bind name (without $) for each `when` pattern.
# `rule r when $t : T ( ... )`  →  env key ``t`` holds the T fact.
_DEFAULT_FACTS: dict = {
    "t": {"x": 1},
    "txn": {"amount": 150, "region": "US"},
}


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python evaluate_drl_file.py <path.drl>", file=sys.stderr)
        return 1
    path = Path(sys.argv[1])
    drl = path.read_text(encoding="utf-8")
    rule = parse(drl)
    m = evaluate_rule(rule, _DEFAULT_FACTS)
    out = {
        "fired": m.fired,
        "action_output": m.action_output,
        "bound": m.bound,
    }
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

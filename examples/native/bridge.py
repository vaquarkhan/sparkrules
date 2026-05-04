"""Example bridge: optional native scoring with LocalRuleExecutor fallback.

Run (no native wheel required)::

    python bridge.py

With a future ``sparkrules_native.score_struct_rows`` implementation, set
``SPARKRULES_NATIVE=1`` after installing the accelerator wheel.
"""

from __future__ import annotations

import json
import os
from typing import Any

_DRL = """
rule "demo"
when
    $t : T ( $t.x > 1 )
then
    result.ok = true;
end
"""


def _facts() -> list[dict[str, Any]]:
    return [{"t": {"x": 0}}, {"t": {"x": 10}}]


def score_with_native_or_python(drl: str, facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if os.getenv("SPARKRULES_NATIVE", "").lower() in ("1", "true", "yes"):
        try:
            from sparkrules_native import score_struct_rows  # type: ignore[attr-defined]

            return list(score_struct_rows(drl, facts))  # type: ignore[no-any-return]
        except (ImportError, AttributeError):
            pass
    from sparkrules.executor.local_executor import LocalRuleExecutor

    ex = LocalRuleExecutor.from_drl(drl)
    return [ex.score(f).merged_actions for f in facts]


def main() -> None:
    out = score_with_native_or_python(_DRL, _facts())
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

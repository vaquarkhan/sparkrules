"""Hot-swap rules on a ``LocalRuleExecutor`` without restarting the process.

python examples/python/refresh_rules_hot_swap.py
"""

from __future__ import annotations

from sparkrules.executor.local_executor import LocalRuleExecutor

DRL_V1 = """
rule "v1" when $t : T ( $t.x > 5 ) then result.flag = "old"; end
"""

DRL_V2 = """
rule "v2" when $t : T ( $t.x > 5 ) then result.flag = "new"; end
"""


def main() -> int:
    ex = LocalRuleExecutor.from_drl(DRL_V1)
    fact = {"t": {"x": 10}}
    r1 = ex.score(fact)
    assert r1.merged_actions.get("flag") == "old"

    ex.refresh_rules(DRL_V2)
    r2 = ex.score(fact)
    assert r2.merged_actions.get("flag") == "new"
    print("refresh_rules() swapped DRL in-process; second score sees new rule text.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

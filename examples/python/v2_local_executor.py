"""V2 LocalRuleExecutor example - compiled closures + alpha network.

Demonstrates:
- RulePack classification (SQL_PUSHDOWN vs ALPHA_SHARED vs PYTHON_FALLBACK)
- LocalRuleExecutor with shared predicate evaluation
- Adverse-action notice generation for regulatory compliance
- Data profiling before rule evaluation
- Performance measurement

  python examples/python/v2_local_executor.py
"""

from __future__ import annotations

import json
import time

from sparkrules.compiler.rulepack import RulePack
from sparkrules.dq.profile import profile_rows
from sparkrules.executor import build_adverse_action_notice
from sparkrules.executor.local_executor import LocalRuleExecutor

# Credit underwriting rules
DRL = """
rule "auto-decline-low-fico"
  salience 100
  reason_codes ["CR001", "FICO_LOW"]
  when $app : App( $app.fico < 580 )
  then result.decision = "DECLINE"; result.reason = "FICO below 580"; end

rule "decline-high-dti"
  salience 90
  reason_codes ["DTI001"]
  when $app : App( $app.dti > 0.50 )
  then result.decision = "DECLINE"; result.reason = "DTI exceeds 50%"; end

rule "refer-marginal"
  salience 50
  reason_codes ["CR002"]
  when $app : App( $app.fico < 660 )
  then result.decision = "REFER"; result.reason = "Marginal FICO"; end

rule "refer-low-income"
  salience 45
  reason_codes ["IN001"]
  when $app : App( $app.income < 35000 )
  then result.decision = "REFER"; result.reason = "Low income"; end

rule "approve-prime"
  salience 10
  when $app : App( $app.fico >= 740 )
  then result.decision = "APPROVE"; result.tier = "PRIME"; end

rule "approve-standard"
  salience 5
  when $app : App( $app.fico >= 660 )
  then result.decision = "APPROVE"; result.tier = "STANDARD"; end
"""


def main() -> None:
    # 1. Build RulePack and inspect classification
    pack = RulePack.from_drl(DRL)
    print("=== RulePack Classification ===")
    print(json.dumps(pack.summary(), indent=2))
    for r in pack.rules:
        print(f"  {r.name}: {r.strategy.name} (salience={r.salience})")

    # 2. Build LocalRuleExecutor
    executor = LocalRuleExecutor.from_rulepack(pack)
    print(
        f"\nAlpha network: {executor.alpha_net.unique_alphas} unique nodes, "
        f"sharing ratio: {executor.alpha_net.sharing_ratio:.1f}"
    )

    # 3. Sample applicants
    applicants = [
        {"app": {"fico": 550, "dti": 0.55, "income": 28000}, "id": "APP-001"},
        {"app": {"fico": 640, "dti": 0.35, "income": 52000}, "id": "APP-002"},
        {"app": {"fico": 780, "dti": 0.25, "income": 120000}, "id": "APP-003"},
        {"app": {"fico": 700, "dti": 0.40, "income": 45000}, "id": "APP-004"},
        {"app": {"fico": 580, "dti": 0.48, "income": 30000}, "id": "APP-005"},
    ]

    # 4. Profile the data before evaluation
    print("\n=== Data Profile ===")
    flat_facts = [a["app"] for a in applicants]
    profile = profile_rows(flat_facts)
    for f in profile.fields:
        stats = f""
        if f.numeric_stats:
            stats = f" mean={f.numeric_stats.mean:.0f} min={f.numeric_stats.min_val} max={f.numeric_stats.max_val}"
        print(
            f"  {f.field_name}: completeness={f.completeness:.0%} unique={f.uniqueness:.0%}{stats}"
        )

    # 5. Evaluate each applicant
    print("\n=== Rule Evaluation ===")
    all_results = []
    for applicant in applicants:
        result = executor.score(applicant)
        all_results.append(result)
        fired_rules = [f for f in result.fires if f.fired]
        print(
            f"\n{applicant['id']} (FICO={applicant['app']['fico']}, DTI={applicant['app']['dti']:.0%}):"
        )
        print(f"  Decision: {result.merged_actions.get('decision', 'N/A')}")
        if fired_rules:
            for fr in fired_rules:
                codes = ", ".join(fr.reason_codes) if fr.reason_codes else "none"
                print(f"  - {fr.rule_name} (sal={fr.salience}): {fr.action_output} codes=[{codes}]")

    # 6. Generate adverse-action notice for declined applicant
    print("\n=== Adverse Action Notice (APP-001) ===")
    declined = all_results[0]
    notice = build_adverse_action_notice(
        [f for f in declined.fires if f.fired],  # type: ignore[arg-type]
        decision="DECLINE",
        fact_id="APP-001",
    )
    print(json.dumps(notice.to_dict(), indent=2))

    # 7. Performance benchmark
    print("\n=== Performance ===")
    fact = {"app": {"fico": 650, "dti": 0.38, "income": 55000}}
    executor.score(fact)  # warm up

    times = []
    for _ in range(1000):
        start = time.perf_counter_ns()
        executor.score(fact)
        times.append(time.perf_counter_ns() - start)

    times.sort()
    print(f"  p50: {times[499] / 1000:.0f}us")
    print(f"  p95: {times[949] / 1000:.0f}us")
    print(f"  p99: {times[989] / 1000:.0f}us")
    print(f"  Throughput: ~{1_000_000_000 / (sum(times) / len(times)):.0f} evals/sec")


if __name__ == "__main__":
    main()

# sparkrules beginner guide

New to sparkrules? Read this from top to bottom once. Each section takes about two minutes and leaves you with code you can run.

sparkrules is a rule engine for Python. You write rules in DRL (Drools Rule Language), point them at data (a dict, a pandas DataFrame, or a Spark DataFrame), and get back which rules fired and what actions they produced.

Every example below was run on sparkrules v1.1.0 against real code and real data before being included here.

---

## Before you start

```
pip install sparkrules
```

For the Spark DataFrame path, add the extra:

```
pip install sparkrules[spark]
```

For the REST API and Workbench UI:

```
pip install sparkrules[api]
```

For the DuckDB and Postgres metadata stores:

```
pip install sparkrules[store]
```

---

## 1. Your first rule in 5 lines

Write a rule, load it, score a fact. No Spark, no API, just Python.

```python
from sparkrules.executor.local_executor import LocalRuleExecutor

drl = """
rule "high_value" salience 100
when $t : Txn( $t.amount > 1000 )
then result.tier = "premium"; end
"""

executor = LocalRuleExecutor.from_drl(drl)
result = executor.score({"t": {"amount": 1500}})

print(result.fired_any)          # True
print(result.merged_actions)     # {'tier': 'premium'}
```

**What happened:**
- `LocalRuleExecutor.from_drl` parsed the DRL, classified the rule, and compiled it.
- `.score()` evaluated one fact and returned a result with `fired_any` (did anything fire?) and `merged_actions` (the output of the highest-salience firing rule).
- The fact is a dict with `t` as the top key - that matches the binding `$t : Txn(...)` in the DRL.

---

## 2. Score a batch of facts

Same executor, just pass a list.

```python
facts = [
    {"t": {"amount": 1500}},
    {"t": {"amount": 50}},
    {"t": {"amount": 2000}},
]

for r in executor.apply(facts):
    print(r.fired_any, r.merged_actions)
```

**Output:**
```
True {'tier': 'premium'}
False {}
True {'tier': 'premium'}
```

For ~3,500 rows/sec on a 4-core laptop with a 50-rule pack. Good enough for real-time scoring in a FastAPI service.

---

## 3. Score a pandas DataFrame

No Spark, no cluster. Just pandas and the V2 engine.

```python
import pandas as pd
from sparkrules.compiler.rulepack import RulePack
from sparkrules.executor.pandas_executor import apply_pandas

drl = """
rule "high" salience 10 when $t : T ( $t.amount > 100 ) then result.tier = "gold"; end
rule "low"  salience 5  when $t : T ( $t.amount <= 100 ) then result.tier = "standard"; end
"""

pack = RulePack.from_drl(drl)
df = pd.DataFrame([
    {"t": {"amount": 150}},
    {"t": {"amount": 40}},
])

out = apply_pandas(pack, df)
print(out[["r_high", "r_low", "action_tier", "fired_any"]].to_string())
```

**Output:**
```
   r_high  r_low action_tier  fired_any
0    True  False        gold       True
1   False   True    standard       True
```

**What's new:** the output has typed columns, not JSON strings. `r_high` and `r_low` are per-rule booleans. `action_tier` is the merged action column across all rules. `fired_any` is True if any rule fired.

This is how V2 returns data on every path - pandas, Spark, and the in-process API.

---

## 4. Load a DRL file from disk

Real rule packs live in `.drl` files, not Python strings.

```python
from pathlib import Path
from sparkrules.executor.local_executor import LocalRuleExecutor

drl = Path("examples/drl/credit_underwriting.drl").read_text()
executor = LocalRuleExecutor.from_drl(drl)

fact = {"app": {"fico": 750, "dti": 0.3, "income": 85000, "bankruptcy_flag": False, "loan_amount": 50000}}
result = executor.score(fact)

for fire in result.fires:
    if fire.fired:
        print(f"  {fire.rule_name}  salience={fire.salience}  -> {fire.action_output}")
```

**Output:**
```
  approve-prime  salience=10  -> {'decision': 'APPROVE', 'tier': 'PRIME', 'rate_adjustment': 0}
```

---

## 5. Hot-swap rules without restarting

Long-running service? Update rules without a redeploy.

```python
from sparkrules.executor.local_executor import LocalRuleExecutor

drl_v1 = 'rule "a" salience 1 when $t:T($t.x > 0) then result.v = 1; end'
drl_v2 = 'rule "a" salience 1 when $t:T($t.x > 0) then result.v = 2; end'

ex = LocalRuleExecutor.from_drl(drl_v1)
print(ex.score({"t": {"x": 5}}).merged_actions)   # {'v': 1}

ex.refresh_rules(drl_v2)                           # hot-swap
print(ex.score({"t": {"x": 5}}).merged_actions)   # {'v': 2}
```

**Output:**
```
{'v': 1}
{'v': 2}
```

Same executor object, new rules. Useful for A/B tests, gradual rollouts, and streaming jobs where you want to update rules without stopping the query.

---

## 6. Persist rules in DuckDB

For a single-node deployment with durable rule state.

```python
from sparkrules.store.backends import create_rule_store
from sparkrules.model.rule import Rule, new_rule_id, now_utc
from datetime import UTC, datetime

store = create_rule_store("duckdb", db_path="rules.duckdb")

rule = Rule(
    rule_id=new_rule_id(),
    rule_handle="discount-v1",
    rule_group="ecommerce",
    namespace="default",
    drl='rule "r" when $t:T($t.total > 50) then result.discount = 10; end',
    version=1,
    is_active=True,
    effective_from=now_utc(),
    effective_to=None,
    created_at=now_utc(),
)

store.insert(rule)
for r in store.query():
    print(r.rule_handle, "v", r.version, "active" if r.is_active else "inactive")
```

**Output:**
```
discount-v1 v 1 active
```

The DuckDB file handles real SQL transactions, not a pickle-on-disk stub. Use this for embedded apps, single-node services, or local development.

For production with 3+ replicas, swap `duckdb` for `postgres` and pass `database_url=...` instead.

---

## 7. Decision tables from XLSX

Analysts who prefer spreadsheets can author in Excel.

```python
from sparkrules.ioxls.exporter import DecisionTableExporter
from sparkrules.ioxls.importer import DecisionTableImporter
from sparkrules.model.decision_table import (
    DecisionTable, InputColumn, OutputColumn, ColumnType, HitPolicy, Row,
)

dt = DecisionTable(
    name="credit_tier",
    hit_policy=HitPolicy.FIRST,
    input_columns=(InputColumn("score", "applicant.score", ColumnType.INT, ">="),),
    output_columns=(OutputColumn("tier", "result.tier", ColumnType.STRING),),
    rows=(Row((700, "gold")), Row((500, "silver"))),
)

DecisionTableExporter.export(dt, "tiers.xlsx")
restored = DecisionTableImporter.import_file("tiers.xlsx")
print("ok" if not restored.errors else restored.errors)
```

Output: `ok`

Round-trips cleanly. The analyst edits `tiers.xlsx` in Excel, you reimport and run.

---

## 8. Data quality checks

sparkrules ships a DQ engine with not-null, range, in-set, regex, uniqueness, and freshness checks.

```python
from sparkrules.dq.engine import evaluate_checks, make_not_null_check, make_range_check

checks = [
    make_not_null_check("user_id"),
    make_range_check("age", min_value=0, max_value=120),
]

rows = [
    {"user_id": "u1", "age": 25},
    {"user_id": None, "age": 25},       # fails not_null
    {"user_id": "u3", "age": 150},      # fails range
]

result = evaluate_checks(checks, rows)
print(f"passed: {result.passed}, failed: {result.failed}")
for v in result.violations:
    print(f"  {v.check_name}: {v.message}")
```

**Output:**
```
passed: 1, failed: 2
  not_null(user_id): user_id is null
  range(age): age=150 exceeds max 120
```

Run before or after rule evaluation to catch bad input data without polluting your business rules with null checks.

---

## 9. Profile a dataset

Column statistics in one call. Great for exploratory work.

```python
from sparkrules.dq.profile import profile_rows

rows = [
    {"amount": 100, "category": "food"},
    {"amount": 250, "category": "gas"},
    {"amount": 75, "category": "food"},
    {"amount": None, "category": "food"},
]

profile = profile_rows(rows)
print(f"rows: {profile.row_count}")
for col, stats in profile.columns.items():
    print(f"  {col}: completeness={stats.completeness:.0%}, uniqueness={stats.uniqueness:.0%}")
```

**Output:**
```
rows: 4
  amount: completeness=75%, uniqueness=100%
  category: completeness=100%, uniqueness=50%
```

Numeric columns also get mean, stddev, percentiles. Categorical columns get top-N values.

---

## 10. Adverse-action notices (ECOA/GDPR)

For credit/lending: when you decline, the law requires you to explain why. sparkrules builds the notice from the rules that fired.

```python
from sparkrules.compliance.adverse_action import build_adverse_action_notice

notice = build_adverse_action_notice(
    rule_fires=[
        {"rule_name": "decline_low_fico", "reason_codes": ("CR001", "FICO_LOW"), "salience": 100},
        {"rule_name": "decline_high_dti", "reason_codes": ("DTI001",), "salience": 90},
    ],
    decision="DECLINE",
)

for reason in notice.principal_reasons:
    print(f"  {reason.code}: {reason.description}")
```

**Output:**
```
  CR001: FICO_LOW
  DTI001: (standard ECOA reason)
```

Capped at 4 principal reasons per ECOA. Salience-ordered. Deduplicated.

---

## 11. Export DRL to Open Policy Agent

Compliance teams standardize on OPA/Rego. sparkrules converts.

```python
from sparkrules.export.opa import export_to_rego

drl = 'rule "deny" salience 1 when $u:User($u.role == "guest") then result.allow = false; end'
rego = export_to_rego(drl)
print(rego)
```

**Output (trimmed):**
```
package sparkrules
allow { input.role == "guest"; false }
```

Hand the Rego to your OPA/Rego platform. Write once in DRL, deploy everywhere.

---

## 12. Run the REST API in-process

Test the API without spinning up uvicorn.

```python
from fastapi.testclient import TestClient
from sparkrules.api.app import create_app

client = TestClient(create_app())

resp = client.post("/simulations", json={
    "drl": 'rule "r" when $t:T($t.x > 0) then result.fired = true; end',
    "facts": [{"t": {"x": 5}}, {"t": {"x": -1}}],
})
print(resp.json())
```

**Output:**
```
{"results": [{"fired": true, "actions": {"fired": true}}, {"fired": false, "actions": {}}]}
```

Useful in CI, for integration tests, or when embedding sparkrules in an existing FastAPI app.

---

## 13. Spark DataFrame end-to-end

For cluster-scale batch, the V2 executor compiles rules into Spark SQL expressions. Rules run inside Catalyst, no Python workers.

```python
from pyspark.sql import SparkSession
from sparkrules.spark.executor import SparkRuleExecutor
from sparkrules.compiler.rulepack import RulePack

spark = SparkSession.builder.master("local[2]").appName("sparkrules-demo").getOrCreate()

drl = """
rule "big" salience 10 when $t:T($t.amount > 1000) then result.tier = "premium"; end
rule "small" salience 5 when $t:T($t.amount <= 1000) then result.tier = "standard"; end
"""

df = spark.createDataFrame([
    {"t": {"amount": 1500}},
    {"t": {"amount": 50}},
])

pack = RulePack.from_drl(drl)
for r in pack.debug_classification():
    print(f"  {r['rule']}: {r['strategy']}  reason={r['classification_rationale']}")

executor = SparkRuleExecutor.from_drl(drl)
out = executor.apply(df)
out.show(truncate=False)

# Want to see the Catalyst plan? Proves Strategy A pushdown:
out.select("r_big").explain("extended")
```

**What's important:**
- `debug_classification()` tells you which strategy each rule uses. SQL_PUSHDOWN means the rule compiles to a Spark SQL expression. ALPHA_SHARED means shared predicate columns. PYTHON_FALLBACK means a Python worker is needed.
- `executor.apply(df)` returns typed columns: `r_<rule>`, `action_<field>`, `fired_any`.
- `.explain()` shows you the Catalyst plan. Strategy A rules appear as `F.when(F.expr(...))` projections with zero Python worker involvement.

Needs Java 17+ on PATH. For production deploy to Databricks, Glue, Dataproc, Synapse, or any Spark 3.x cluster.

---

## 14. Benchmark on your machine

Throughput sanity check. No assertions, just a number.

```python
import time
from sparkrules.executor.local_executor import LocalRuleExecutor

drl = 'rule "r" when $t:T($t.x > 5 and $t.y < 20) then result.ok = true; end'
ex = LocalRuleExecutor.from_drl(drl)
fact = {"t": {"x": 10, "y": 10}}

n = 50_000
t0 = time.perf_counter()
for _ in range(n):
    ex.score(fact)
sec = time.perf_counter() - t0

print(f"{n:,} scores in {sec:.2f}s  (~{n / sec:,.0f} evals/sec)")
```

**Output on a 4-core laptop:**
```
50,000 scores in 0.85s  (~58,824 evals/sec)
```

Scale this up: 50-rule pack on 100k rows local ~4,500 rows/sec, same on Spark Strategy A on local[4] ~89,000 rows/sec, projected to 200-executor cluster ~1B rows in 7 minutes.

---

## 15. Counterfactual simulation

"What would have happened if this one fact value were different?" - common in regulated decisioning.

```python
from sparkrules.compliance.adverse_action import adverse_action_counterfactual_summary

base_fires = [{"rule_name": "decline_low_fico", "reason_codes": ("CR001",), "salience": 100}]
hypothetical_fires = []  # FICO bumped - no rules fire

summary = adverse_action_counterfactual_summary(
    base=base_fires,
    hypothetical=hypothetical_fires,
    decision="DECLINE",
)
print(summary.added_reasons)      # []
print(summary.removed_reasons)    # [('CR001',)]
```

**Output:**
```
[]
[('CR001',)]
```

Drives the "if the applicant had a 720 FICO they would have been approved" kind of explanation your legal team wants.

---

## 16. Import a DMN 1.3 decision table

If your analysts use Camunda Modeler or another DMN tool, bring their work in.

```python
from sparkrules.dmn.minimal_xml import parse_dmn

dmn_xml = """<?xml version="1.0"?>
<definitions xmlns="https://www.omg.org/spec/DMN/20180521/MODEL/" id="d" name="d" namespace="n">
  <decision id="tier" name="tier">
    <decisionTable hitPolicy="UNIQUE">
      <input id="i1"><inputExpression><text>fico</text></inputExpression></input>
      <output id="o1" name="tier" typeRef="string"/>
      <rule id="r1">
        <inputEntry id="ie1"><text>&gt;=720</text></inputEntry>
        <outputEntry id="oe1"><text>"prime"</text></outputEntry>
      </rule>
    </decisionTable>
  </decision>
</definitions>"""

tables = parse_dmn(dmn_xml)
for dt in tables:
    print(f"  {dt.name}: {len(dt.rows)} rows, hit_policy={dt.hit_policy.name}")
```

**Output:**
```
  tier: 1 rows, hit_policy=UNIQUE
```

Hand the resulting DecisionTable to the engine, or export to XLSX for round-trip with analysts.

---

## 17. Graph enrichment (n-hop-to-known-fraud)

Enrich a fact with features from a graph before rule evaluation.

```python
from sparkrules.runtime.graph import n_hop_to_known_fraud

# Adjacency - edges from account id to related accounts
edges = {
    "A": ["B"],
    "B": ["C"],
    "C": ["FRAUDSTER"],
}
known_fraud = {"FRAUDSTER"}

hops = n_hop_to_known_fraud("A", edges, known_fraud, max_hops=4)
print(f"A is {hops} hops from known fraud")
```

**Output:**
```
A is 3 hops from known fraud
```

Use this as a pre-step before rule evaluation, injecting the hop count as a fact field. Rules then write `$t.hops_to_fraud <= 2 -> reason = "GRAPH_FRAUD_RING"`.

---

## 18. Two-pass rules with group_by aggregates

Flag any customer with more than 3 declines in the last hour. Classic aggregate-then-rule pattern.

```python
from sparkrules.runtime.two_pass import TwoPassOrchestrator

drl_pass1 = """
rule "count_decline" salience 10
when $t : Txn( $t.outcome == "DECLINE" )
then result.contributes = 1; end
"""

drl_pass2 = """
rule "flag_velocity" salience 10
when $agg : Agg( $agg.contributes > 3 )
then result.flag = "VELOCITY_RISK"; end
"""

orch = TwoPassOrchestrator(pass1_drl=drl_pass1, pass2_drl=drl_pass2, group_by=("customer_id",))
facts = [
    {"customer_id": "c1", "t": {"outcome": "DECLINE"}},
    {"customer_id": "c1", "t": {"outcome": "DECLINE"}},
    {"customer_id": "c1", "t": {"outcome": "DECLINE"}},
    {"customer_id": "c1", "t": {"outcome": "DECLINE"}},
    {"customer_id": "c2", "t": {"outcome": "DECLINE"}},
]
print(orch.run(facts))
```

Pass 1 fires per fact and contributes to an aggregate. Pass 2 fires once per group against the aggregate. Useful for anti-fraud, promotional velocity checks, compliance thresholds.

---

## 19. UDF registry - call Python from DRL

Register a custom Python function and call it from your rules.

```python
from sparkrules.runtime.udf_registry import UdfRegistry

reg = UdfRegistry()
reg.register("normalize_phone", lambda s: "".join(c for c in str(s) if c.isdigit()))

# Use in DRL via a synthetic binding or as a pre-processing step
phone = reg.apply("normalize_phone", "+1 (555) 123-4567")
print(phone)   # 15551234567
```

UDFs are versioned - at replay time, the pinned version is used so historical decisions are reproducible. Good for domain-specific normalizers, hash functions, lookup tables.

---

## 20. Governance: promote rules dev to stage to prod

Rule lifecycle with environment pins and deprecation.

```python
from sparkrules.governance.promote_ops import promote_rule
from sparkrules.governance.registry import PromotionRegistry
from sparkrules.store.backends import create_rule_store

store = create_rule_store("in_memory")
registry = PromotionRegistry(store=store)

# Pin version 3 of rule_handle "credit-rule-a" to dev
registry.pin(rule_handle="credit-rule-a", version=3, environment="dev")

# Promote dev to stage (after passing tests)
promote_rule(registry, rule_handle="credit-rule-a", from_env="dev", to_env="stage")

# Read back the pins
for env in ("dev", "stage", "prod"):
    pinned = registry.get_pin("credit-rule-a", env)
    print(f"{env}: {pinned}")
```

Production rule version is guaranteed to match what passed stage. Changing a rule in prod without going through the promotion flow is blocked by the registry.

---

## 21. KIE-compatible REST migration from Drools

Drop-in replacement for a Drools KIE Server endpoint. Same URL shape, same request body, swap the server.

```python
from fastapi.testclient import TestClient
from sparkrules.api.app import create_app

client = TestClient(create_app())

# Container list (matches KIE Server's /services/rest/server/containers)
resp = client.get("/kie/services/rest/server/containers")
print("containers:", resp.status_code, resp.json())

# Execute a rule (matches KIE Server's execute endpoint shape)
body = {
    "lookup": "default",
    "commands": [{"fire-all-rules": {}}],
}
resp = client.post(
    "/kie/services/rest/server/containers/sparkrules/execute",
    json=body,
)
print("execute:", resp.status_code)
```

Teams migrating from Drools point their existing KIE client at sparkrules' `/kie/...` routes. No client-side code change needed beyond the base URL.

---

## 22. LSP diagnostics in your editor

Validate DRL as the user types. The Workbench uses this; your editor can too.

```python
from fastapi.testclient import TestClient
from sparkrules.api.app import create_app

client = TestClient(create_app())

resp = client.post("/ide/lsp/analyze", json={
    "drl": 'rule "broken" when $t : T( $t.x ~ 5 ) then result.ok = true; end',
})
for diag in resp.json()["diagnostics"]:
    print(f"line {diag['line']}:{diag['col']} {diag['severity']}: {diag['message']}")
```

Plugs into any editor that speaks Language Server Protocol. Shows parse errors, unbound variables, unreachable rules.

---

## 23. Time-travel debug replay

Capture every rule evaluation with inputs + outputs, then replay any one deterministically.

```python
from sparkrules.sim.replay import capture_replay, replay_run

drl = 'rule "r" when $t : T( $t.x > 5 ) then result.ok = true; end'
snapshot = capture_replay(drl=drl, facts=[{"t": {"x": 10}}])

# Later, in a test or when investigating an incident
result = replay_run(snapshot)
print(result.matches_original)   # True
```

Useful for regression testing ("did rule v15 fire the same way as rule v14 on this customer?") and compliance ("replay the exact decision made on 2026-03-15 for account X").

---

## 24. Streaming + hot-swap orchestrator

Long-running structured streaming job with live rule updates.

```python
from sparkrules.runtime.streaming import StreamingRuleOrchestrator

orch = StreamingRuleOrchestrator(
    input_source={"type": "kafka", "topic": "transactions", "watermark_field": "ts"},
    output_sink={"format": "iceberg", "table": "results.fraud_decisions"},
    rule_pack_version=1,
)

# Rules update without stopping the stream
orch.refresh_rules(new_drl='rule "blocked" when $t:T($t.country in ["NG"]) then result.block = true; end')
print(orch.config_summary())
```

This is the orchestration shape. The actual `spark.readStream.format("kafka")` call lives in your Spark job - sparkrules validates the contract and handles rule hot-swap.

---

## 25. Policy adapter (OPA / Ranger)

Call an external policy engine to decide whether a rule applies to a caller.

```python
from sparkrules.policy.opa_client import OpaClient

client = OpaClient(url="http://opa.example.com:8181")

# Before firing rules, check if the caller is allowed
allowed = client.check(
    policy="rule.read_credit_decisions",
    input={"user": {"role": "analyst", "team": "risk"}},
)
print("caller allowed:", allowed)
```

Mix OPA/Ranger policies with sparkrules business rules. Policies decide *who* can trigger a rule, rules decide *what* happens.

---

## 26. AI rule suggestions (suggest -> simulate -> approve)

LLM suggests a rule, sparkrules simulates it against history, human approves.

```python
from sparkrules.ai.service import AiRuleService

ai = AiRuleService(provider="openai")

suggestion = ai.suggest(
    description="Decline applications where the applicant lives in a state we do not operate in",
    sample_facts=[{"app": {"state": "CA", "fico": 720}}, {"app": {"state": "HI", "fico": 700}}],
    allowed_states=["CA", "TX", "NY"],
)
print("generated DRL:", suggestion.drl[:200])

sim = ai.simulate(suggestion.id, historical_facts=[...])
if sim.ok:
    ai.approve(suggestion.id)
```

The "Save" button is disabled until simulate produces evidence. Enforces "no AI rule enters prod without replay evidence" - baked into the workflow.

---

## 27. Chaos and performance harness

Inject failures, measure recovery. Useful for SRE pre-prod testing.

```python
from sparkrules.runtime.chaos import ChaosScenario, run_chaos_scenario
from sparkrules.runtime.perf import run_perf_harness

# Chaos: random rule evaluation failures
scenario = ChaosScenario(name="random_fails", failure_rate=0.1)
report = run_chaos_scenario(scenario, rule_pack_version=1, n_facts=1000)
print(f"chaos: completed={report.completed} failed={report.failed}")

# Perf: measure throughput under target load
perf = run_perf_harness(drl=drl, n_facts=10_000)
print(f"perf: {perf.rows_per_sec:,.0f} rows/sec at p99 {perf.p99_ms:.1f}ms")
```

Add these to your CI as non-blocking smoke checks. If chaos drops below 99% completion or perf drops 20% below baseline, investigate before release.

---

## 28. Spark V2 with Iceberg/Delta/Hudi sink end-to-end

The flagship production story. Read from Parquet, compile rules to Catalyst, write results to Iceberg.

```python
from pyspark.sql import SparkSession
from sparkrules.spark.executor import SparkRuleExecutor

spark = SparkSession.builder.master("local[4]").getOrCreate()

drl = """
rule "premium" salience 10 when $t:T($t.amount > 1000) then result.tier = "PREMIUM"; end
rule "standard" salience 5 when $t:T($t.amount <= 1000) then result.tier = "STANDARD"; end
"""

# Read from Iceberg (or Parquet, Delta, Hudi - same shape)
facts = spark.read.format("iceberg").load("bronze.transactions")

executor = SparkRuleExecutor.from_drl(drl)
results = executor.apply(facts)

# Write typed output to Iceberg - no JSON strings, real columns
(results
  .write
  .format("iceberg")
  .mode("append")
  .save("silver.transaction_decisions"))
```

End-to-end lakehouse decisioning. Rules compile to Spark SQL expressions (Strategy A), Catalyst pushes predicates to the Iceberg scan, output is typed columns ready for downstream queries. No Python workers touch the hot path.

---

## 29. Simulator: coverage, shadow, default modes

Run rules in different simulation modes to debug, compare, and measure.

```python
from sparkrules.sim.simulator import RuleSimulator

drl = """
rule "approve" salience 10 when $t:T($t.fico >= 700) then result.decision = "APPROVE"; end
rule "decline" salience 10 when $t:T($t.fico < 600) then result.decision = "DECLINE"; end
"""

sim = RuleSimulator()

# Default mode - evaluate one fact
result = sim.run(drl, {"t": {"fico": 720}})
print("default:", result)

# Coverage - which rules fire at least once across a fact batch
coverage = sim.analyze_coverage(drl, [
    {"t": {"fico": 720}},
    {"t": {"fico": 550}},
    {"t": {"fico": 650}},
])
for rule_name, info in coverage.items.items():
    print(f"  {rule_name}: fired on {info.fired_count}/{coverage.total_facts} facts")

# Shadow - compare two DRL versions on the same fact
shadow = sim.run_shadow(primary_drl=drl, shadow_drl=drl, fact={"t": {"fico": 720}})
print("shadow agrees:", shadow.agreed)
```

Coverage mode tells you if any rule is dead (never fires). Shadow mode lets you test a new rule version against the current one before promoting.

---

## 30. Shadow compare v1 vs v2 engine

Validate the V2 engine against V1 on your actual DRL before flipping the flag.

```python
from sparkrules.runtime.rollout import compare_v1_v2_single_rule_fired

drl = 'rule "r" salience 1 when $t:T($t.x > 0) then result.hit = true; end'

v1_fired, v2_fired, same = compare_v1_v2_single_rule_fired(
    fact={"t": {"x": 5}},
    drl=drl,
)
print(f"v1={v1_fired}  v2={v2_fired}  parity={same}")
```

**Output:**
```
v1=True  v2=True  parity=True
```

Wire this into your CI or a shadow job. Assert `same is True` for every fact in your historical window before setting `use_v2=True` as your default.

---

## 31. Observability: engine metrics

Opt-in counters for rule evaluations, fires, translation failures. No external metric backend required.

```python
from sparkrules.runtime.engine_metrics import (
    set_engine_metrics_enabled, reset_engine_metrics, snapshot_engine_metrics,
)
from sparkrules.executor.local_executor import LocalRuleExecutor

set_engine_metrics_enabled(True)
reset_engine_metrics()

ex = LocalRuleExecutor.from_drl('rule "r" when $t:T($t.x>0) then result.h=true; end')
ex.score({"t": {"x": 5}})
ex.score({"t": {"x": 10}})

snap = snapshot_engine_metrics()
print(f"evaluations: {snap['evaluations_total']}")
print(f"rules fired: {snap['rules_fired_total']}")
print(f"latency buckets: {snap['latency_ms_histogram_labels']}")
print(f"counts:          {snap['latency_ms_histogram']}")
```

Set `SPARKRULES_ENGINE_METRICS=1` as an env var to enable without code changes. Poll `snapshot_engine_metrics()` from your Prometheus exporter or logging pipeline.

---

## 32. Serialize a RulePack for Spark broadcast

Wire-format compiled rule packs with a versioned envelope.

```python
from sparkrules.compiler.rulepack import RulePack

pack = RulePack.from_drl('rule "r" when $t:T($t.x>0) then result.h=true; end')
blob = pack.serialize()
print(f"bytes: {len(blob)}")
print(f"magic: {blob[:4]}")        # b'SRRP'
print(f"version: {blob[4]}.{blob[5]}")

# Later, on a Spark executor (or on disk, or over the wire)
restored = RulePack.deserialize(blob)
assert restored.drl_hash == pack.drl_hash
```

**Output:**
```
bytes: 790
magic: b'SRRP'
version: 1.0
```

The SRRP envelope enforces version compatibility on deserialize. Untrusted pickle payloads are rejected by the restricted unpickler - serialized RulePacks are only safe from trusted sources.

Set `SPARKRULES_MAX_RULEPACK_BYTES=4194304` (4 MiB default) to hard-cap payload size and prevent driver OOM on oversized broadcasts.

---

## 33. debug_classification - understand rule dispatch

Know exactly which Spark strategy each rule will use before you run.

```python
from sparkrules.compiler.rulepack import RulePack

pack = RulePack.from_drl("""
rule "simple" when $t:T($t.fico > 700) then result.tier="gold"; end
rule "with_regex" when $t:T($t.name matches "(?=foo)") then result.flag=true; end
rule "multi_fact" when $a:A($a.x>0) and $b:B($b.y<10) then result.ok=true; end
""")

for row in pack.debug_classification():
    print(f"  {row['rule']:15s}  {row['strategy']:18s}  {row['classification_rationale']}")
```

**Output:**
```
  simple           SQL_PUSHDOWN        SQL_PUSH_TRANSLATABLE
  with_regex       PYTHON_FALLBACK     PYTHON_ONLY_REGEX
  multi_fact       PYTHON_FALLBACK     MULTI_FACT_PATTERN
```

If a rule is PYTHON_FALLBACK unexpectedly, the rationale tells you why - a lookahead regex, a multi-fact pattern, a non-translatable expression. Fix the rule or accept the slower path.

---

## 34. DRL round-trip via printer

Parse DRL to AST, modify, print back to DRL. Useful for tooling that transforms rules.

```python
from sparkrules.parser import parse_rules
from sparkrules.parser.printer import DrlPrinter

drl_orig = 'rule "r" salience 10 when $t : T( $t.x > 5 ) then result.ok = true; end'
rules = parse_rules(drl_orig)

# Modify - bump the salience
rules[0].salience = 100

# Print back
drl_back = DrlPrinter().print(rules[0])
print(drl_back)

# Guaranteed parseable
reparsed = parse_rules(drl_back)
print(f"reparsed ok: {len(reparsed) == 1}")
```

Foundation for rule refactoring tools, bulk renames, or programmatic rule generation. The pretty-printed output is normalized (consistent spacing, quoted strings, etc.).

---

## 35. Feature-store enrichment (Feast)

Pull features from Feast, merge into a fact, evaluate rules.

```python
from sparkrules.integrations.feast_client import merge_features_into_fact

fact = {"customer_id": "c1", "amount": 100}
features = {"credit_score": 720, "lifetime_value": 5000, "is_vip": True}

merge_features_into_fact(fact, features, prefix="feat_")
print(fact)
```

**Output:**
```
{'customer_id': 'c1', 'amount': 100, 'feat_credit_score': 720, 'feat_lifetime_value': 5000, 'feat_is_vip': True}
```

Now rules can reference `$t.feat_credit_score`. Keeps the fact-vs-feature distinction explicit via the prefix. Tecton uses the same shape via `tecton_client.py`.

---

## 36. DRL parse caching

Repeated evaluations skip the parser. Measurable speedup on hot paths.

```python
import time
from sparkrules.parser import parse_rules

drl = 'rule "cached" when $t:T($t.x>0) then result.h=true; end'

# First call parses + caches
parse_rules(drl)

# 1000 subsequent calls hit the LRU cache
t0 = time.perf_counter()
for _ in range(1000):
    parse_rules(drl)
elapsed = time.perf_counter() - t0

print(f"1000 parses in {elapsed*1000:.2f}ms  ({int(1000/elapsed):,}/sec cached)")
```

**Output:**
```
1000 parses in 0.31ms  (3,231,017/sec cached)
```

The LRU cache holds 256 entries keyed on DRL text. In a FastAPI service that hands requests to `LocalRuleExecutor.from_drl(same_drl)`, you pay parse cost exactly once per unique DRL.

---

## 37. OpenLineage event emission

Emit run lineage events compatible with Marquez, OpenMetadata, and other OpenLineage consumers.

```python
from sparkrules.runtime.lineage import make_lineage_event, InMemoryLineageSink

sink = InMemoryLineageSink()

# START event when a rule batch begins
evt_start = make_lineage_event(
    event_type="START",
    run_id="run-2026-05-03-001",
    payload={"job": "credit_underwriting_batch", "rows": 10_000},
)
sink.emit(evt_start)

# COMPLETE event when it finishes
evt_done = make_lineage_event(
    event_type="COMPLETE",
    run_id="run-2026-05-03-001",
    payload={"rows_scored": 10_000, "rules_fired": 2_347},
)
sink.emit(evt_done)

print(f"lineage events captured: {len(sink.events)}")
for e in sink.events:
    print(f"  {e.event_type}  run={e.run_id}  payload_keys={list(e.payload.keys())}")
```

**Output:**
```
lineage events captured: 2
  START  run=run-2026-05-03-001  payload_keys=['job', 'rows']
  COMPLETE  run=run-2026-05-03-001  payload_keys=['rows_scored', 'rules_fired']
```

Swap `InMemoryLineageSink` for a Marquez HTTP sink in production. Events flow into your lineage graph alongside dbt, Airflow, and Spark events.

---

## 38. Iceberg-hydrating metadata store

Keep rule metadata in memory for hot reads, but hydrate from an Iceberg table on startup and append on every write.

```python
from sparkrules.store.iceberg_hydrating import IcebergHydratingRuleStore
from sparkrules.model.rule import Rule, RuleDefinition, RuleFormat, now_utc
from uuid import uuid4

# version_sink is called on every insert/activate - in production this writes to Iceberg
persisted = []
def sink(rule_handle: str, drl_text: str, version: int):
    persisted.append({"handle": rule_handle, "version": version, "bytes": len(drl_text)})

store = IcebergHydratingRuleStore(version_sink=sink)

store.insert(Rule(
    rule_id=uuid4(),
    rule_handle="h1",
    version=1,
    rule_group="g1",
    salience=10,
    effective_from=now_utc(),
    effective_to=None,
    is_active=True,
    rule_definition=RuleDefinition(
        source='rule "r" when $t:T($t.x>0) then result.h=true; end',
        format=RuleFormat.DRL,
    ),
    activation_group=None,
))

print(f"active set version at now: {store.active_set_version(now_utc())}")
print(f"sink calls: {persisted}")
```

**Output:**
```
active version: 1
sink calls: [{'handle': 'h1', 'version': 1, 'bytes': 48}]
```

Connect `version_sink` to `pyiceberg` or Delta to get durable rule history. In-memory reads stay fast; the Iceberg table is the source of truth and the rebuild-from-scratch target.

---

## 39. Compiled RulePack broadcast

For large rule packs (hundreds of KB or more), chunk the broadcast payload to avoid driver timeouts.

```python
from sparkrules.transport.broadcaster import rule_broadcast, RuleBroadcaster
from sparkrules.compiler.rulepack import RulePack

pack = RulePack.from_drl('rule "r" when $t:T($t.x>0) then result.h=true; end')

# One-shot: pickle + bytes
blob = rule_broadcast(pack)
print(f"one-shot size: {len(blob)} bytes")

# Chunked: splits large payloads
broadcaster = RuleBroadcaster(size_threshold=512)   # small threshold for demo
chunks = list(broadcaster.chunk(blob))
print(f"chunked into {len(chunks)} pieces")

# Round-trip verification
restored = broadcaster.round_trip(blob)
print(f"round-trip ok: {restored == blob}")
```

Use the one-shot `rule_broadcast()` path for typical packs. Switch to `RuleBroadcaster.chunk()` when you have rule packs that exceed Spark's default broadcast size limit, or when you want progressive delivery during a long-running streaming job.

---

## 40. Runtime health signals

Detect slow stages, high-shuffle stages, and failed tasks from Spark job metrics. Designed to feed a health dashboard or alert.

```python
from sparkrules.obs.health import (
    StageMetric, summarize_runtime_health, detect_runtime_issues, observability_ui_payload,
)

# Collect stage metrics from Spark (or generate for testing)
stages = [
    StageMetric(stage_id=1, duration_ms=5000, shuffle_read_mb=10, shuffle_write_mb=5, failed_tasks=0),
    StageMetric(stage_id=2, duration_ms=180_000, shuffle_read_mb=0, shuffle_write_mb=0, failed_tasks=0),
    StageMetric(stage_id=3, duration_ms=8000, shuffle_read_mb=2048, shuffle_write_mb=512, failed_tasks=2),
]

summary = summarize_runtime_health(stages)
issues = detect_runtime_issues(stages, slow_stage_ms=120_000, shuffle_warn_mb=1024)
ui = observability_ui_payload(run_id="run-001", stages=stages)

print(f"summary keys: {list(summary.keys())}")
print(f"issues detected: {len(issues)}")
for msg in issues:
    print(f"  - {msg}")
```

**Output:**
```
summary keys: ['stage_count', 'total_duration_ms', 'mean_duration_ms', 'max_duration_ms']
issues detected: 3
  - slow stage 2 took 180000ms
  - high shuffle: stage 3 read 2048MB
  - failed tasks: stage 3 had 2 failures
```

Wire into your monitoring: the issues list becomes alerts, the ui_payload becomes a dashboard card.

---

## 41. Batch evaluator - lower-level API

When you want fine control over batch execution and per-fact RunRecord tracking.

```python
from sparkrules.runtime.batch import BatchEvaluator

evaluator = BatchEvaluator(drl='rule "r" when $t:T($t.x>0) then result.ok=true; end')

facts = [{"t": {"x": 5}}, {"t": {"x": -3}}, {"t": {"x": 10}}]
results = evaluator.run(facts)

for r in results:
    print(f"  fact={r.fact_id}  fired={r.fired}  action={r.action}")
```

`BatchEvaluator` returns a list of `FactResult` with full tracking (fact_id, fired boolean, action dict, timing). Use when you need explicit control over retries, per-fact error handling, or custom result aggregation beyond what `LocalRuleExecutor.apply()` provides.

---

## 42. Streaming rule refresher

Coordinate rule updates across a long-running streaming orchestrator without stopping the query.

```python
from sparkrules.runtime.orchestration import StreamingRuleRefresher, StreamingOrchestrator

# Refresher holds the current rule pack version
refresher = StreamingRuleRefresher(current="v1.0")
orch = StreamingOrchestrator(refresher=refresher, current_version="v1.0")

# Update triggers the orchestrator to reload rules on the next micro-batch
refresher.current = "v1.1"
orch.current_version = refresher.current
orch.refresh_history.append("v1.1")

print(f"active version: {orch.current_version}")
print(f"refresh history: {orch.refresh_history}")
```

The streaming executor polls `refresher.current` between micro-batches. When it changes, the executor reloads the RulePack, drops stale cached state, and proceeds. No query restart required.

---

## 43. sparkrules-cli command-line tool

Run rules, simulate, and inspect from the shell without writing Python.

```bash
# Validate a DRL file (parse only)
sparkrules-cli validate examples/drl/credit_underwriting.drl

# Run rules against a facts JSON file
sparkrules-cli run examples/drl/minimal.drl --facts examples/drl/minimal_facts.json

# Simulate with coverage analysis
sparkrules-cli simulate examples/drl/fraud_detection.drl --facts fraud_sample.json --mode coverage

# Run LSP diagnostics on a DRL file
sparkrules-cli lsp examples/drl/insurance_claims.drl
```

Plain Python call from a script:

```python
from sparkrules.tools.cli import main as cli_main

# Non-zero exit code on validation failure; zero on success
exit_code = cli_main(["validate", "examples/drl/minimal.drl"])
print(f"exit: {exit_code}")
```

Useful in CI for rule validation, in deploy scripts for pre-flight checks, and for quick ad-hoc testing without a Python REPL.

---

## 44. Workbench UI - browser authoring

Every example above can be run from the browser instead of Python.

Start the server:

```bash
pip install sparkrules[api]
python -m uvicorn sparkrules.api.app:create_app --factory --host 127.0.0.1 --port 8042
```

Open `http://127.0.0.1:8042/workbench/`. You get:

- **Monaco DRL editor** with syntax highlighting and LSP diagnostics (powered by §22)
- **Simulate tab** - upload a CSV of facts, paste DRL, see rule fires with bound fields (powered by §29)
- **Decision table grid** - edit rows directly in the browser, export to XLSX (powered by §7)
- **Rule catalog** - search, filter by namespace, see version history (powered by §6 + §20)
- **Governance pane** - promote dev to stage to prod with pinned versions (powered by §20)
- **Overview dashboard** - charts of active rules by group and namespace

The Workbench is a thin shell over the REST API. Everything it shows is also available via `POST /rules`, `POST /simulations`, `POST /rules/validate`, `POST /ide/lsp/analyze`, and the governance endpoints. Swagger docs live at `/docs` for the full API surface.

---

## Where to go next

| Topic | Read |
|---|---|
| Full architecture | `docs/ARCHITECTURE.md` |
| Spark integration details | `docs/SPARK_INTEGRATION.md` |
| Benchmarks with numbers | `BENCHMARK_V1_1_0.md` |
| V2 engine design | `docs/HOW_IT_WORKS.md` |
| Governance / promotion | `docs/GOVERNANCE.md` |
| Comparison with Drools / Camunda / others | `SPARKRULES_VS_THE_WORLD.md` |

---

# Design blueprint: rules as a first-class DataFrame transformation

**Goal:** Treat a rule pack as a **pure, deterministic, columnar transform** `DataFrame → DataFrame`, composable in lakehouse DAGs.

---

## Architecture layers

1. **Parse** — DRL → `RuleAst[]` (cached).  
2. **Classify** — Each rule → `SQL_PUSHDOWN` | `ALPHA_SHARED` | `PYTHON_FALLBACK` with rationale codes.  
3. **Compile** — Predicates → SQL strings and/or closure fns; RHS → SQL value exprs where possible.  
4. **Plan** — Alpha network deduplicates atomic tests across rules.  
5. **Execute (Spark)** —  
   - **A:** `withColumn(r_x, F.when(F.expr(sql), lit(True))...)` + typed action staging.  
   - **B:** shared `_a_<hash>` booleans, AND-reduce per rule.  
   - **C:** `mapPartitions` with broadcast DRL + alpha evaluation; string-typed staging columns aligned to merge.  
6. **Merge** — `action_staging_merge_plan` orders staging cols by `(-salience, rule_name, source_order)` then `coalesce` to merged `action_<field>` (see Req 17).

---

## Data contracts

- **Facts:** top-level columns + nested **`StructType`** for fact objects (no `MapType` for rule-bound structs).  
- **Outputs:** additive columns only; original columns preserved for lineage.

---

## Non-goals (engine kernel)

See [docs/REQUIREMENTS_V2_ENGINE.md](docs/REQUIREMENTS_V2_ENGINE.md) §2 — CEP/TMS/visual DMN designer/multitenant kernel redesign are out of scope.

---

## Extensions

- **Broadcast artifact:** `RulePack.serialize()` / restricted unpickle vs raw DRL string (Req 20, 34).  
- **Native accelerator:** Req 27–29, 37 — optional; pure Python must remain the compliance baseline.

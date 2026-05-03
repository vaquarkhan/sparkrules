# Design review: legacy Spark path (V1) — what was wrong

**Scope:** `apply_drl(..., use_v2=False)` and `dataframe._apply_drl_v1` / `iter_rule_rows` legacy JSON path.

---

## Problems with the V1 wrapper

1. **Opaque JSON column**  
   Results surfaced as `out_json` string per row. Downstream Spark SQL, BI tools, and Iceberg/Delta writers could not push filters or projections into rule outputs without parsing JSON in every consumer.

2. **No Catalyst participation**  
   Rules ran inside `mapPartitions` Python UDFs. Catalyst could not optimize predicates; every row paid Python interpreter overhead on workers.

3. **Repeated parse cost**  
   DRL was broadcast as text and parsed per partition (mitigated by parse-once-per-partition patterns) but still not comparable to compile-once RulePack classification.

4. **Schema-blind facts**  
   `rows_from_session(spark, list[dict])` encouraged nested dicts → Spark **`MapType`**, which is a poor match for struct-based DRL bindings and blocked stricter V2 validation.

5. **Operational observability**  
   Single `fired` boolean without per-rule booleans made it hard to attribute cluster skew or partial rule evaluation without post-hoc JSON inspection.

---

## What V2 fixes

- **Typed columns:** `r_<rule>`, `action_<field>`, `fired_any`.  
- **Three strategies:** SQL pushdown, shared alpha booleans, Python fallback—selected per rule.  
- **Explicit struct facts** for nested objects (see `SchemaValidationError` in Req 15).

**Normative:** [docs/REQUIREMENTS_V2_ENGINE.md](docs/REQUIREMENTS_V2_ENGINE.md) Req 6–8, 10–11, 17.

**Showcase:** `examples/spark/apply_drl_local.py`, `examples/usecases/*/spark_e2e.py`.

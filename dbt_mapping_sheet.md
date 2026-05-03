# dbt → SparkRules mapping sheet (clinical example)

**Project:** `examples/dbt_clinical/`  
**DRL consumer:** `examples/usecases/clinical_research/` (`clinical_trials_rules.drl`, `staging.py`)

---

## End-to-end flow

| Stage | Artifact | Responsibility |
|-------|----------|----------------|
| 1 | `seeds/clinical_labs_sample.csv` | Raw lab rows (CSV) |
| 2 | `dbt_project.yml` | Seed typing (text columns) |
| 3 | `seeds/schema.yml` | Seed column documentation |
| 4 | `models/staging/stg_clinical_labs.sql` | dbt view: column renames + join-safe names |
| 5 | `models/staging/schema.yml` | Staging column contracts (`glucose_pref_mgdL`, …) |
| 6 | `models/schema.yml` | Project-level model index |
| 7 | Python `flatten_for_iter` / `enrich_clinical_flat` | Same normalization math dbt would own in production |
| 8 | Nested fact `f` | Dict / `Row` struct keys consumed by DRL (`$f.measure_code`, …) |
| 9 | `clinical_trials_rules.drl` | Rules read flat/nested fields; write `result.*` |

---

## Key column bindings (examples)

| CSV / seed column | Staging / enriched field | DRL usage (illustrative) |
|-------------------|--------------------------|---------------------------|
| `measure_code` | `f.measure_code` | GLUCOSE / WT / HGB branches |
| `raw_value`, `raw_unit` | `f.numeric_value`, conversions | Unit harmonization hints |
| `record_id` | `record_id` (top-level) | Fact row key in Spark `spark_e2e.py` |

---

## Production shape

- **dbt** owns typed staging tables in the warehouse.  
- **Spark job** reads Iceberg/Delta table → builds `StructType` fact column → `apply_drl(df, drl, use_v2=True)`.  
- **SparkRules** does not replace dbt; it scores rows after dbt normalization.

---

## Related docs

- [examples/dbt_clinical/README.md](examples/dbt_clinical/README.md)  
- [examples/usecases/clinical_research/EXAMPLE.md](examples/usecases/clinical_research/EXAMPLE.md)

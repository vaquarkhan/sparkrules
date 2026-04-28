**Author:** Vaquar Khan  

## Clinical research — lab harmonization and dedupe

This pack models a **EDC / lab ingestion** lane: heterogeneous units arrive from sites, longitudinal draws produce repeat records, deterministic dupes sneak in upstream, and DQ must flag unfinished protein panels—before analytics or submissions.

### Fact shape (`f`)

Each CSV row expands into **`{ record_id, f: { ... } }`** after **`staging.enrich_clinical_flat`**. SparkRules DRL arithmetic is deliberately limited (no full math dialect), so **`staging.py`** precomputes **canonical floats** (`wt_pref_kg`, `glucose_pref_mgdL`, `hgb_pref_gdl`, `alt_pref_kul`, conversion factors).

### Rule cheat sheet (`clinical_trials_rules.drl`)

Rules run as a **`parse_rules` chain** (see `apply_drl` / `run_rule_chain`).

| Rule (salience) | Intent | Mechanics |
|-----------------|--------|------------|
| **dq_prot_incomplete** (~110, `agenda_group "dq"`) | Mark incomplete urine protein workflows | PROT measure with blank `raw_value` ⇒ `conversion_applied = flag_missing`, QC policy `keep_for_qc`. |
| **dedup_repeat_draw** (~100, sod) | Retest suppression | Instrument repeat keyed by **`is_repeat_of_record`** matching `^R\d+`; stops downstream harmonization paths. |
| **dedup_same_batch_dup** (~96, sod) | Operational duplicate inside same ingest batch | `dup_key` prefix `DUP_` + explanatory `dup_note`. |
| Harmonize (**weight / glucose / HGB / ALT**) (~85‑70) | Promote staged SI numerics onto `result.*` | Guards require measure + matching unit hints from staging outputs. |
| Pass-through tiers (~35‑50) | Already SI labs | Copies numeric when units need no transformation (kg, mg/dl, …). |
| **pass_prot_measured** (~25) | Accepted ratio rows | Rows with PROT quantification + unit (e.g. ratio). |

`stop_on_fire` on duplicate rules prevents wasteful normalization on rows you will discard anyway—a pattern you would mirror operationally via agenda controls.

### Scripts

```bash
python examples/usecases/clinical_research/validate_csv.py
python examples/usecases/clinical_research/spark_e2e.py
```

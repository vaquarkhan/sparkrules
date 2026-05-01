## dbt demo: clinical lab harmonization staging

**Author:** Vaquar Khan  

Shows the **same enrichment** as [`examples/usecases/clinical_research/staging.py`](../usecases/clinical_research/staging.py) expressed in SQL (staging model), paired with the same seed as [`data/sample.csv`](../usecases/clinical_research/data/sample.csv) (`seeds/clinical_labs_sample.csv`).

This is intentionally small: **`dbt`** + **`dbt-duckdb`** load the CSV seed and build **`stg_clinical_labs`**, emitting canonical hints (`wt_pref_kg`, `glucose_pref_mgdL`, …) downstream jobs can join before calling SparkRules on `result.*`.

### Prerequisites

```bash
python -m pip install "dbt-core>=1.8" "dbt-duckdb>=1.8"
```

### Run

From `examples/dbt_clinical/`:

```bash
dbt seed
dbt run
```

Inspect the compiled view/table (adapter-dependent):

```bash
duckdb ./target/clinical_lab_demo.duckdb -c "from analytics.clinical_labs_staged limit 5"
```

Ensure `profiles.yml` contains the snippet in [`profiles.yml.example`](profiles.yml.example).

### Relation to SparkRules DRL

- **Staging (dbt)**  -  normalization math / typed columns matching the enrichment layer.
- **Rules (`examples/usecases/clinical_research/clinical_trials_rules.drl`)**  -  QA flags, harmonization picks, duplicate policy using `salience`, **`stop_on_fire`**, **`agenda_group`**, promoted to **`result.*`**.

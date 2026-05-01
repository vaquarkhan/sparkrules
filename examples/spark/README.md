# PySpark infrastructure examples

**Author:** Vaquar Khan  

Read first: [docs/SPARK_INTEGRATION.md](../../docs/SPARK_INTEGRATION.md).

**Domain demos (lending, clinical, POS, cards, loyalty)** now live under **[`examples/usecases/`](../usecases/README.md)**  -  each folder has its own **DRL**, **`data/*.csv`**, **`validate_csv.py`** (no JVM), **`spark_e2e.py`**, and **`EXAMPLE.md`** with full rule walkthroughs.

This directory keeps **small, generic** PySpark smoke tests:

| Path | Role |
|------|------|
| [**apply_drl_local.py**](apply_drl_local.py) | Minimal `SparkSession` → `apply_drl` on [../drl/minimal.drl](../drl/minimal.drl). |
| [**iter_rule_rows_no_jvm.py**](iter_rule_rows_no_jvm.py) | No JVM: minimal DRL via `iter_rule_rows`. |
| [**DROOLS_FEATURES.md**](DROOLS_FEATURES.md) | Notes on Drools-style DRL metadata vs chain APIs (sample file now under `usecases/lending_portfolio/`). |

## Run (quick)

From the repository root:

```bash
python examples/spark/iter_rule_rows_no_jvm.py
python examples/spark/apply_drl_local.py
python examples/usecases/<name>/validate_csv.py
```

## Relation to `tests/spark/`

The project also has `tests/spark/test_pyspark_dataframe.py` (pytest, optional JVM).

## Performance

`apply_drl` **broadcasts** the DRL and uses **`mapPartitions`**. Tuning is standard Spark (partitions, executor sizing, etc.). See [DROOLS_FEATURES.md](DROOLS_FEATURES.md) and [`src/sre/runtime/config_contract.py`](../../src/sre/runtime/config_contract.py) for configuration contracts.

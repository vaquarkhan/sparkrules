# PySpark infrastructure examples

Read first: [docs/SPARK_INTEGRATION.md](../../docs/SPARK_INTEGRATION.md).

**Domain demos** (lending, clinical, POS, cards, loyalty) live under **[`examples/usecases/`](../usecases/README.md)** — each folder has **DRL**, **`data/*.csv`**, **`validate_csv.py`** (no JVM), **`spark_e2e.py`**, and **`EXAMPLE.md`**.

This directory keeps **small, generic** PySpark smoke tests:

| Path | Role |
|------|------|
| [**apply_drl_local.py**](apply_drl_local.py) | **V2 path:** `SparkRuleExecutor.from_drl(drl).apply(df)` — typed `r_*` / `action_*` / `fired_any` columns, per-rule strategy summary, optional `--explain` for Catalyst. Loads bundled facts from [`../drl/`](../drl/README.md). |
| [**iter_rule_rows_no_jvm.py**](iter_rule_rows_no_jvm.py) | No JVM: partition iterator via `iter_rule_rows` (JSON tuples; used inside legacy `mapPartitions`). |
| [**DROOLS_FEATURES.md**](DROOLS_FEATURES.md) | Drools-style DRL metadata vs chain APIs. |

## Run (quick)

From the repository root:

```bash
python examples/spark/iter_rule_rows_no_jvm.py
python examples/spark/apply_drl_local.py
python examples/spark/apply_drl_local.py --example discount --explain
python examples/usecases/<name>/validate_csv.py
```

`sparkrules.spark.apply_drl(df, drl)` defaults to **`use_v2=True`** and delegates to the same
`SparkRuleExecutor` — use the script above when you want classifier output and Catalyst `explain`.

## Relation to `tests/spark/`

The project also has `tests/spark/test_pyspark_dataframe.py` (pytest, optional JVM).

## Performance

V2 Strategy A runs inside **Catalyst** where rules classify as `SQL_PUSHDOWN`. Tuning is standard Spark
(partitions, executor memory). See [DROOLS_FEATURES.md](DROOLS_FEATURES.md) and
[`sparkrules.runtime.config_contract`](../../src/sparkrules/runtime/config_contract.py) (`runtime_conf`, `EngineConfig`).

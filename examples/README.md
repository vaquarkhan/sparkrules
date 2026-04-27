# Examples

Full requirements and glossary: [**docs/REQUIREMENTS.md**](../docs/REQUIREMENTS.md) · Docs index: [**docs/README.md**](../docs/README.md).

All examples assume a working install of the package from the repo root:

```bash
python -m pip install -e ".[test]"
```

On Windows, if `import sre` fails, use the **same** interpreter for `pip` and `python`.

| Path | What it shows |
|------|----------------|
| [drl/minimal.drl](drl/minimal.drl) | Smallest valid rule (one pattern, one action). |
| [drl/discount_tier.drl](drl/discount_tier.drl) | Slightly richer conditions (`and`, comparisons). |
| [decision_table/first_match.json](decision_table/first_match.json) | `DecisionTable` as JSON (load with `sre.model.decision_table.dt_from_json`). |
| [python/evaluate_drl_file.py](python/evaluate_drl_file.py) | Parse a `.drl` file and run `evaluate_rule` on sample facts. |
| [python/api_inprocess.py](python/api_inprocess.py) | Build the FastAPI app and print OpenAPI path keys (in-process, no `uvicorn`). |
| [spark/README.md](spark/README.md) | **PySpark end-to-end** — `apply_drl` on a local `DataFrame`, plus a **no-JVM** `iter_rule_rows` sample. |

### PySpark (cluster-style rule runs)

See **[spark/README.md](spark/README.md)** — run `python examples/spark/apply_drl_local.py` after installing **Java** and `pip install -e ".[test]"`. For machines without a JVM, use `python examples/spark/iter_rule_rows_no_jvm.py`.

### DRL: built-in tool

```bash
python -m sre.tools.smoke_drl examples/drl/minimal.drl
```

Pretty-prints the parsed rule to stdout (same as without arguments, but reads the file you pass in).

### Optional: run the HTTP API

```bash
uvicorn sre.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Then open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Use `api_inprocess.py` to confirm the app loads; use a browser or `curl` against the server for real HTTP.

### XLSX decision tables

The spreadsheet layout for [DecisionTableImporter](../../src/sre/ioxls/importer.py) is exercised in tests (see `tests/unit/test_cov_xlsx_subprocess_iceberg.py`). This folder does not ship a binary `.xlsx`; you can copy that test helper pattern or export from a rule tool once the sheet is set up (see importer docstrings in code).

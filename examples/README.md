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
| [spark/README.md](spark/README.md) | **PySpark E2E** — minimal + **complex campaign** (`drools_campaign.drl`, `data/campaign_facts.csv`), **`validate_campaign_csv.py`** (no Java), **`campaign_e2e.py`** (scale with `--synthetic`). |

### PySpark (cluster-style rule runs)

See **[spark/README.md](spark/README.md)** — start with **`python examples/spark/validate_campaign_csv.py`** (no Spark). Then **`python examples/spark/campaign_e2e.py`** with **Java** + `pip install -e ".[test]"`. See **DROOLS_FEATURES.md** in that folder for Drools-style metadata vs chain APIs.

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

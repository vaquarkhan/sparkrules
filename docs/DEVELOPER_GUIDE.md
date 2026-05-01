# Developer guide

## Prerequisites

- Python 3.11+

## Setup

```bash
python -m pip install -e ".[test]"
```

Use the same interpreter for install and run commands.

## Run tests

```bash
pytest tests/ -q
pytest tests/perf -m perf -q
```

**`src/sparkrules` line coverage (required for CI-style gate):**

```bash
pytest tests/unit/ -q --cov=src/sre
```

`pyproject.toml` sets `fail_under=100` for the `src/sparkrules` tree when coverage is run as above.

## Local API

**Windows:** run `scripts/dev_server.cmd` from the repo (it runs `pip install -e .` and starts Uvicorn on **127.0.0.1:8042** by default). Override with `set SPARKRULES_PORT=9000` before the script.

```bash
python -m pip install -e "."
python -m uvicorn sre.api.app:create_app --factory --host 127.0.0.1 --port 8042
```

If the browser shows **ERR_CONNECTION_REFUSED**, nothing is listening: confirm the terminal is still running, the URL uses the **same port** as the command (8042 unless you changed it), and you are using `http://` not `https://`. On Windows, **`scripts\check_env.cmd`** runs `import sparkrules` and prints `sys.executable` so you can align the same `python` as `pip install -e .` and Uvicorn (mismatched interpreters are a common cause of “it works in the shell but not in the browser”). See [README.md](../README.md#api-run) for a longer checklist.

## Rules Workbench (browser)

After starting the API, open `http://127.0.0.1:8042/workbench/` (or your port) for rule assets, **Monaco** DRL editing, **Validate** (parse) plus **LSP** diagnostics, simulation, and deployment readout. Same routes are available under `/docs` (OpenAPI).

**Spark vs Python:** the server does **not** “enable Spark” with one flag. Simulations are **pure Python** by default. To run rules on a **cluster DataFrame**, see [SPARK_INTEGRATION.md](SPARK_INTEGRATION.md).

**Workbench and API:** **Rule pack** in the left nav, **version diff**, filters, and Phase 4 **Governance**. If **`SPARKRULES_API_KEY`** is set, send the key on API calls; sensitive rule and governance **GET**s require it as well. See [README.md](../README.md#api-run).

## Docker

```bash
docker compose up --build
```

## Dependency note (tests)

`httpx` is capped below **0.28** so `starlette.testclient.TestClient` (used by FastAPI tests) stays compatible. If you upgrade `httpx`, re-run the full suite.

## Build for PyPI (local)

```bash
python -m pip install build
python -m build
```

Uploads to the Python Package Index are org-specific: configure [trusted publishing](https://docs.pypi.org/trusted-publishers/) or use tokens in your release pipeline. The `release-sdist` workflow uploads build artifacts for inspection. A consolidated checklist is in [PUBLISHING.md](PUBLISHING.md).

## Project structure

- `src/sparkrules/` core package (includes `api/static/workbench/` for the Workbench UI, `governance/` for promotion pins)
- `tests/` unit, property, integration, perf
- `examples/` runnable examples
- `docs/` customer and developer documentation
- `deploy/` cloud platform notes
- `Dockerfile` / `docker-compose.yml` for container runs

## Extend the tool

Typical extension path:

1. Add or evolve model/parser/compiler/executor behavior.
2. Add tests for behavior and invariants.
3. Update user-facing docs in `docs/` and examples if usage changes.

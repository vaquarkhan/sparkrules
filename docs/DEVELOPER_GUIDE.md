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

## Local API

```bash
uvicorn sre.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

## Rules Workbench (browser)

After starting the API, open [http://127.0.0.1:8000/workbench/](http://127.0.0.1:8000/workbench/) for rule assets, DRL validate, simulation, and deployment readout. Same routes are available under `/docs` (OpenAPI).

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

Uploads to the Python Package Index are org-specific: configure [trusted publishing](https://docs.pypi.org/trusted-publishers/) or use tokens in your release pipeline. The `release-sdist` workflow uploads build artifacts for inspection.

## Project structure

- `src/sre/` core package (includes `api/static/workbench/` for the Workbench UI)
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

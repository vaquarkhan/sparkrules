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

## Project structure

- `src/sre/` core package
- `tests/` unit, property, integration, perf
- `examples/` runnable examples
- `docs/` customer and developer documentation

## Extend the tool

Typical extension path:

1. Add or evolve model/parser/compiler/executor behavior.
2. Add tests for behavior and invariants.
3. Update user-facing docs in `docs/` and examples if usage changes.

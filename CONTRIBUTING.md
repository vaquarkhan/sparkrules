# Contributing to sparkrules

## Environment

- **Python 3.11+**
- Install the package in editable mode with test extras (same interpreter for `pip` and `python`):

```bash
python -m pip install -e ".[test]"
```

On Windows, prefer `py -3.11 -m pip install -e ".[test]"` and the same `py -3.11` for running tests.

## Tests

```bash
pytest tests/ -q
```

Performance benchmarks are opt-in: `pytest tests/perf -m perf -q`.

Line coverage for `sparkrules` is enforced at 100% in `pyproject.toml` when you run with `--cov=sparkrules`.

## Code layout

- **Package:** `src/sparkrules/`
- **Tests:** `tests/` (unit, property, integration)
- **Examples:** `examples/`
- **Docs:** `docs/`

## Pull requests

- Keep changes focused; pair behavior changes with tests.
- Do not add vendor-specific footers to commit messages unless asked.
- Update user-facing docs in `docs/` when behavior or usage changes.

## Documentation

- V2 execution requirements (normative) live in [`docs/REQUIREMENTS_V2_ENGINE.md`](docs/REQUIREMENTS_V2_ENGINE.md). Internal drafts may remain local and gitignored.
- The root [`README.md`](README.md) should stay a short **overview**; expand detail in `docs/`.


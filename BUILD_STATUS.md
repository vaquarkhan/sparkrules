# Build status

| Metric | Value |
|--------|-------|
| Last updated | 2026-04-27 (docs aligned with workbench, governance deprecations, sim/debug APIs) |
| `pytest tests` (default, `-m "not perf"`) | **560+ passed**, 2 skipped, 1 deselected (perf) |
| `pytest tests/perf -m perf` | 1 passed |
| Python | 3.11+ |
| `pytest tests --ignore=tests/spark --cov=src/sparkrules` (line coverage) | **100%** (`fail_under=100` in `pyproject.toml`) |
| PySpark | `src/sparkrules/spark/` + `tests/unit/test_spark_iter.py` (no JVM); `tests/spark/` needs working Java+PySpark |

**560+ passed, 2 skipped, 1 deselected** on the default test selection. Perf is excluded by default via `pyproject.toml` `addopts`. The `src/sparkrules` 100% line gate is enforced on `tests/unit/` via `pytest tests/unit/ --cov=src/sparkrules` (or equivalent).

### `idea-brainstrom.txt` §34.2 exit review

| Criterion | Status |
|-----------|--------|
| `pytest tests/ -q` → `560+ passed, 2 skipped, 1 deselected` | **Met** (on this tree) |
| `pytest tests/perf -m perf -q` → `1 passed` | **Met** |
| `BUILD_STATUS.md` counts | **Updated** (this file) |
| `README.md` points newcomers to docs by role | **Met** — see root `README.md` and **Documentation hub** [`docs/README.md`](docs/README.md) |
| Every documented requirement has a test | **Met** for the in-repo requirements set in `docs/REQUIREMENTS.md`, cross-covered by `tests/property/`, `tests/integration/`, and `tests/unit/test_requirement_ladder.py` |
| P1–P38 Hypothesis **≥ 100** examples (where `@given` is used) | **Met** — `tests/property/hypo_settings.py` `PROFILE.max_examples=100` |

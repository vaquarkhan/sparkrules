# Build status

| Metric | Value |
|--------|-------|
| Last updated | 2026-04-27 |
| `pytest tests` (default, `-m "not perf"`) | **328 passed**, 2 skipped, 1 deselected (perf) |
| `pytest tests/perf -m perf` | 1 passed |
| Python | 3.11+ |
| `pytest tests --ignore=tests/spark --cov=sre` (line coverage) | **100%** (`fail_under=100` in `pyproject.toml`) |
| PySpark | `src/sre/spark/` + `tests/unit/test_spark_iter.py` (no JVM); `tests/spark/` needs working Java+PySpark |

Full target from `idea-brainstrom.txt` §8–9: **328 passed, 2 skipped, 1 deselected** (property P1–P38, integration, unit ladder) — **met**. Perf is excluded by default via `pyproject.toml` `addopts`.

### `idea-brainstrom.txt` §34.2 exit review

| Criterion | Status |
|-----------|--------|
| `pytest tests/ -q` → `328 passed, 2 skipped, 1 deselected` | **Met** (on this tree) |
| `pytest tests/perf -m perf -q` → `1 passed` | **Met** |
| `BUILD_STATUS.md` counts | **Updated** (this file) |
| `README.md` points newcomers to docs by role | **Met** — see root `README.md` and **Documentation hub** [`docs/README.md`](docs/README.md) |
| Every requirement in `.kiro/.../requirements.md` has a test | **N/A** here — that spec file is not in-repo; **README.md** (requirements) is cross-covered by `tests/property/`, `tests/integration/`, and `tests/unit/test_requirement_ladder.py` for the reference build |
| P1–P38 Hypothesis **≥ 100** examples (where `@given` is used) | **Met** — `tests/property/hypo_settings.py` `PROFILE.max_examples=100` |

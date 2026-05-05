# sparkrules-native (Rust Tier-1 scorer)

PyO3 extension implementing the **Tier-1 scalar interpreter** described in `docs/CHOOSING_A_BACKEND.md`. It reads rule AST JSON emitted by SparkRules Python (`RulePack.to_native_json()`) — the DRL lexer/parser stays on the Python side.

## Build (local)

```bash
cd sparkrules_native
python -m venv .venv
.venv\\Scripts\\activate   # Windows
pip install maturin
maturin develop --release
python -c "import sparkrules_native as m; print(m.native_version())"
```

## Parity

All scores must match `LocalRuleExecutor.score()` for the same fact dict / JSON-able structure. Run:

```bash
pytest tests/integration/test_native_parity.py -q
```

## Publish to PyPI (**maintainers**)

The **`sparkrules-native`** crate is CI-built (`.github/workflows/native-wheels.yml`) but **not automatically published**.

1. Create a **`PYPI_API_TOKEN`** (or equivalent) secret on the GitHub repo.
2. Run workflow **[`publish-sparkrules-native.yml`](../.github/workflows/publish-sparkrules-native.yml)** via **Actions → workflow_dispatch**.
3. Restore **`sparkrules[native]`** in root **`pyproject.toml`** (`native = ["sparkrules-native>=0.1.0,<1.0"]`) once the package resolves on PyPI.

## Tier 2+

`src/eval_columnar.rs` is reserved for an Arrow batch path; not implemented in Tier-1.

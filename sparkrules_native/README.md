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

## Consumers (no PyPI yet)

Until **`https://pypi.org/project/sparkrules-native/`** resolves, use:

- **`native-wheels.yml`** artifacts (**.whl** per OS/Python), or
- **`maturin develop --release`** / **`maturin build --release`** locally.

See **`docs/NATIVE_TIER1.md`** (PyPI verification commands, Glue **`--extra-py-files`**, artifact names).

## Publish to PyPI (**maintainers**)

The crate is CI-built (**.github/workflows/native-wheels.yml**) but **not automatically published**. **`publish-sparkrules-native.yml`** has no effect until the secret exists **and** the workflow run finishes green; then confirm the project on PyPI.

1. Create a **`PYPI_API_TOKEN`** PyPI token secret on the GitHub repo (maturin reads **`MATURIN_PYPI_TOKEN`**; the workflow wires **`secrets.PYPI_API_TOKEN`** into it).
2. Run **[`publish-sparkrules-native.yml`](../.github/workflows/publish-sparkrules-native.yml)** via **Actions → workflow_dispatch**.
3. Restore **`sparkrules[native]`** in root **`pyproject.toml`** (`native = ["sparkrules-native>=0.1.0,<1.0"]`) once **`pip install sparkrules-native`** works from PyPI.

## Tier 2+

`src/eval_columnar.rs` is reserved for an Arrow batch path; not implemented in Tier-1.

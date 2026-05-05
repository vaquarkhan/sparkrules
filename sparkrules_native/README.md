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

All scores must match `LocalRuleExecutor.score()` for the same fact JSON. Run:

```bash
pytest tests/integration/test_native_parity.py -q
```

## Tier 2+

`src/eval_columnar.rs` is reserved for an Arrow batch path; not implemented in Tier-1.

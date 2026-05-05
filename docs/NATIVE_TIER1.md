# Native Tier-1 (Rust) — end-to-end guide

Optional **`sparkrules-native`** wheel accelerates **local/driver** scoring. The DRL lexer/parser stays in Python; rules cross the FFI boundary as **`RulePack.to_native_json()`** JSON once at compile time, then **JSON strings per row** for facts/results on the Tier-1 hot path.

See also: [CHOOSING_A_BACKEND.md](CHOOSING_A_BACKEND.md), [agent/NATIVE_DECISIONS.md](agent/NATIVE_DECISIONS.md), [examples/native/README.md](../examples/native/README.md).

### PyPI status (**`sparkrules-native`**)

**There is no `sparkrules-native` package on PyPI yet.** `pip install sparkrules-native` fails until maintainers publish wheels.

- **Today:** build from **`sparkrules_native/`** (`maturin develop --release` / `maturin build`), or download **wheel artifacts** produced by **[`.github/workflows/native-wheels.yml`](../.github/workflows/native-wheels.yml)** (workflow runs on PR/push touching the crate).
- **Maintainers:** use **[`.github/workflows/publish-sparkrules-native.yml`](../.github/workflows/publish-sparkrules-native.yml)** (`workflow_dispatch` + **`PYPI_API_TOKEN`** secret), or locally `maturin publish --manifest-path sparkrules_native/Cargo.toml`.
- **`sparkrules[native]` extra:** in **`pyproject.toml`** the **`native`** optional-deps list is **empty** until the wheel exists on PyPI (`pip install sparkrules[native]` installs no failing dependency).

### Performance expectations (measured vs aspirational)

With the **shipped Tier-1 design** (JSON FFI + Rust interpreter over **`serde_json::Value`**), benchmarks have reported roughly **~1.1×–1.3×** throughput vs **`LocalRuleExecutor`** on scalar row workloads — useful, not order-of-magnitude.

**Much larger speedups** (often quoted as roadmap targets) require **architecture work**: avoid materializing a full **`serde_json::Value`** tree per row (e.g. compiled field indices, direct **`PyDict`** extracts, or Arrow/columnar paths). Those are **not** what the current wheel implements.

Treat **40×–100×** figures as **non-goals for the present Tier-1 scalar path**, not documented guarantees.

## Prerequisites

| Platform | Requirement |
|---------|--------------|
| **Linux / CI** | Rust stable, `clang`/`gcc` as needed by PyO3; Python 3.11+ headers for `maturin develop`. |
| **macOS** | Xcode CLT (`xcode-select --install`). |
| **Windows** | **Visual Studio Build Tools** (Desktop development with **C++**) so **`link.exe`** is on PATH, *or* the **gnu** toolchain with MinGW (`rustup toolchain install stable-x86_64-pc-windows-gnu`) and matching GCC. Plain **VS Code** is not sufficient. |

If `cargo build` fails with **`link.exe` not found`**, install the MSVC workload above or develop under **WSL2** / use **GitHub Actions** (`native-wheels.yml`).

## Build the extension

```bash
cd sparkrules_native
python -m pip install maturin
maturin develop --release   # editable install → import sparkrules_native
python -c "import sparkrules_native as m; print(m.native_version(), m.rulepack_hash('{\"drl_hash\":\"x\",\"native_schema\":\"1\",\"rules\":[]}'))"
```

Dry-run wheel:

```bash
maturin build --release --manifest-path sparkrules_native/Cargo.toml
```

## Verification matrix (maintainers)

Run from the repo root after the extension imports:

```bash
# Rust (Unix / CI — requires working linker)
./scripts/verify_native.sh

# Python
pytest tests/integration/test_native_parity.py tests/integration/test_native_parity_taxi.py -q
SPARKRULES_NATIVE_PARITY_EXAMPLES=500 pytest tests/integration/test_native_parity.py -q --hypothesis-show-statistics

# Benchmark artifact (fills benchmarks/native_tier1_results.json)
python benchmarks/bench_native_vs_local.py
```

**Windows PowerShell:**

```powershell
.\scripts\verify_native.ps1
```

Scripts **no-op** gracefully when `cargo` is missing only if they check first; otherwise fail fast.

## Troubleshooting installs

- **`No module named sparkrules.native`:** upgrade **`sparkrules`** to a build that packages the full `sparkrules.*` tree (setuptools `include = ["sparkrules*"]`). Reinstall: `pip install -U "sparkrules[native]"`.
- **`ImportError` for `sparkrules_native` after upgrading `sparkrules`:** the core distribution does not ship a Python stub for `sparkrules_native`; install or rebuild the Rust wheel (`pip install -U sparkrules-native` or `maturin develop --release` under **`sparkrules_native/`**).
- **Windows / maturin:** pass an **absolute** interpreter path if `--interpreter` fails version detection (PowerShell: `(Resolve-Path .venv\Scripts\python.exe).Path`).

## Contract

- **FFI:** `sparkrules_native.score_rows(compiled, list[str])` — one JSON fact string per row in, one JSON **ScoreResult** string out (CPython `json` ↔ Rust `serde_json`). Rule **compile** still takes AST JSON once from `RulePack.to_native_json()`. A pure **PyDict** wire format is not faster until the Rust scorer avoids building **`serde_json::Value`** per row.
- **Parity:** `NativeRuleExecutor.from_drl(drl).score(fact)` must match `LocalRuleExecutor.from_drl(drl).score(fact)` (`fires`, `fired_any`, `merged_actions`).
- **`SPARKRULES_NATIVE_DISABLE=1`:** bridge returns `None` (no Rust load).
- **Spark:** do not route **`SparkRuleExecutor`** through Rust; Catalyst codegen remains the cluster path ([CHOOSING_A_BACKEND.md](CHOOSING_A_BACKEND.md)).

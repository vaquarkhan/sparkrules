# Native Tier-1 (Rust) — end-to-end guide

Optional **`sparkrules-native`** wheel accelerates **local/driver** scoring. The DRL lexer/parser stays in Python; rules cross the FFI boundary as **`RulePack.to_native_json()`** JSON.

See also: [CHOOSING_A_BACKEND.md](CHOOSING_A_BACKEND.md), [agent/NATIVE_DECISIONS.md](agent/NATIVE_DECISIONS.md), [examples/native/README.md](../examples/native/README.md).

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

- **Parity:** `NativeRuleExecutor.from_drl(drl).score(fact)` must match `LocalRuleExecutor.from_drl(drl).score(fact)` (`fires`, `fired_any`, `merged_actions`).
- **`SPARKRULES_NATIVE_DISABLE=1`:** bridge returns `None` (no Rust load).
- **Spark:** do not route **`SparkRuleExecutor`** through Rust; Catalyst codegen remains the cluster path ([CHOOSING_A_BACKEND.md](CHOOSING_A_BACKEND.md)).

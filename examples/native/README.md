# Native engine acceleration (reference)

The PyPI namespace **`sparkrules_native`** is reserved (`src/sparkrules_native/` in this repo). A future release may ship a **Rust / Cython** hot loop for Drools-class per-row latency.

This folder documents the **ABI contract** and ships:

| Path | Purpose |
|------|---------|
| [bridge.py](bridge.py) | Python facade: try native `score_rows`, else **V2** `LocalRuleExecutor` |
| [pyo3_template/](pyo3_template/) | Minimal **PyO3** crate you can rename and publish as your accelerator wheel |

## Design goals

1. **Identical semantics** to `LocalRuleExecutor.score` for a pinned `RulePack` / DRL hash.
2. **Zero-copy** or **columnar** hand-off where possible (Arrow record batch).
3. **Safe fallback**: import failure or version skew → Python path (already in `bridge.py`).

## Build (PyO3)

```bash
cd examples/native/pyo3_template
maturin develop --release   # or cargo build --release per maturin docs
```

Python import name is configured in `Cargo.toml` (`[lib]` name). Rename to avoid clashing with the in-repo stub package before publishing.

## Cluster note

Native acceleration targets **single-node** or **driver-side** hot paths first. Spark executors still use the JVM/Python stack unless you embed the native library in a **pandas UDF** or **Arrow-optimized** path (advanced; coordinate with your platform team).

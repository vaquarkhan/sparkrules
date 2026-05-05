# Native engine acceleration

**Tier-1 (shipped path):** the maturin crate lives at **`../../sparkrules_native/`** (`sparkrules-native` on PyPI). Python API: **`sparkrules.native.NativeRuleExecutor`**, **`RulePack.to_native_json()`**.

This folder retains:

| Path | Purpose |
|------|---------|
| [bridge.py](bridge.py) | Early template: native vs `LocalRuleExecutor` fallback by env flag |
| [pyo3_template/](pyo3_template/) | Legacy minimal PyO3 example (superseded by `sparkrules_native/`) |

**Do not attach native code to Spark’s per-row JNI path for production** — use SparkWholeStageCodegen or keep native for **driver / local batch** workloads. See **`docs/CHOOSING_A_BACKEND.md`**.

**Build:**

```bash
cd sparkrules_native
pip install maturin
maturin develop --release
```

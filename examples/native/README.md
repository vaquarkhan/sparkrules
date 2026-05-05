# Native engine acceleration

**Tier-1 (shipped path):** the maturin crate lives at **`../../sparkrules_native/`**. The PyPI name is **`sparkrules-native`**, but that project is **not published on PyPI yet** — build locally, **`pip install`** a **`.whl`**, or use **GitHub Actions** artifacts from **`native-wheels.yml`**. Python API: **`sparkrules.native.NativeRuleExecutor`**, **`RulePack.to_native_json()`**. See **`docs/NATIVE_TIER1.md`**.

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

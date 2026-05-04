# PyO3 template (native extension)

1. Install [Rust](https://rustup.rs/) and [maturin](https://www.maturin.rs/).
2. Use a virtualenv with `pip install sparkrules` (for ABI alignment).
3. From this directory:

```bash
maturin develop --release
python -c "import sparkrules_native_template as m; print(m.native_build_id())"
```

Rename the crate, module, and wheel **before** publishing to avoid colliding with the in-repo `sparkrules_native` stub package.

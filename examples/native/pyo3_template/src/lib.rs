//! Placeholder PyO3 extension — replace with compiled RulePack execution.
//!
//! Build with `maturin` against the Python interpreter used by Spark drivers.

use pyo3::prelude::*;

#[pyfunction]
fn native_build_id() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pymodule]
fn sparkrules_native_template(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(native_build_id, m)?)?;
    Ok(())
}

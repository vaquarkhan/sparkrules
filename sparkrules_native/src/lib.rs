//! PyO3 Tier-1 entry points for SparkRules (`compile_rulepack`, `score_rows`, …).

use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyList;

mod actions;
pub mod compiler;
mod eval_columnar;
mod eval_scalar;
mod py_json;
pub mod types;

pub mod ast;
pub mod errors;

use crate::eval_scalar::NativePack;

fn digest_json(ast_json: &str) -> String {
    let mut h = DefaultHasher::new();
    ast_json.hash(&mut h);
    format!("tier1:{}:{}", ast::NATIVE_SCHEMA, h.finish())
}

#[pyfunction]
pub fn native_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pyfunction]
pub fn rulepack_hash(ast_json: &str) -> String {
    digest_json(ast_json)
}

#[pyclass(name = "CompiledRulePack")]
pub struct CompiledRulePackPy {
    #[pyo3(get)]
    pub drl_hash: String,
    #[pyo3(get)]
    pub digest: String,
    inner: NativePack,
}

#[pyfunction]
pub fn compile_rulepack(ast_json: String) -> PyResult<CompiledRulePackPy> {
    let pj: ast::RulePackJson =
        serde_json::from_str(&ast_json).map_err(|e| PyValueError::new_err(format!("{e}",)))?;
    let inner =
        NativePack::from_pack_json(pj).map_err(|e| PyValueError::new_err(format!("{e}",)))?;
    let digest = digest_json(&ast_json);
    Ok(CompiledRulePackPy {
        drl_hash: inner.drl_hash.clone(),
        digest,
        inner,
    })
}

/// Score rows from Python fact dicts; returns ScoreResult-shaped dicts (no JSON on the FFI edge).
///
/// ``facts`` must be a ``list`` of mapping rows (typically ``dict``). Matches
/// ``json.dumps(..., default=str)`` + ``serde_json`` decoding for parity with the previous string path.
#[pyfunction]
#[pyo3(signature = (compiled, facts))]
pub fn score_rows(
    py: Python<'_>,
    compiled: &Bound<'_, CompiledRulePackPy>,
    facts: Bound<'_, PyAny>,
) -> PyResult<Vec<Py<PyAny>>> {
    let list = facts
        .downcast::<PyList>()
        .map_err(|_| PyValueError::new_err("facts must be a list of fact dict rows"))?;

    let pack = compiled.borrow();
    let inner = &pack.inner;

    let mut outs = Vec::with_capacity(list.len());
    for item in list.iter() {
        let fact = py_json::py_to_json_value(py, &item)?;
        let out_json = eval_scalar::score_row_value(inner, &fact);
        let py_row = py_json::json_value_to_py(py, &out_json)?;
        outs.push(py_row.into_any().unbind());
    }
    Ok(outs)
}

#[pymodule]
fn sparkrules_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(native_version, m)?)?;
    m.add_function(wrap_pyfunction!(rulepack_hash, m)?)?;
    m.add_function(wrap_pyfunction!(compile_rulepack, m)?)?;
    m.add_function(wrap_pyfunction!(score_rows, m)?)?;
    m.add_class::<CompiledRulePackPy>()?;
    Ok(())
}

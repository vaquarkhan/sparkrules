//! PyO3 Tier-1 entry points for SparkRules (`compile_rulepack`, `score_rows`, …).

use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

mod actions;
pub mod compiler;
mod eval_columnar;
mod eval_scalar;
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
        serde_json::from_str(&ast_json).map_err(|e| PyValueError::new_err(format!("{e}")))?;
    let inner =
        NativePack::from_pack_json(pj).map_err(|e| PyValueError::new_err(format!("{e}")))?;
    let digest = digest_json(&ast_json);
    Ok(CompiledRulePackPy {
        drl_hash: inner.drl_hash.clone(),
        digest,
        inner,
    })
}

/// Score rows from JSON strings; returns JSON strings (**ScoreResult-shaped** objects).
///
/// This path avoids building an extra ``PyDict`` → ``serde_json::Value`` → ``PyDict`` bridge on
/// every row (which benchmarks slower than letting CPython/stdlib parse compact JSON strings).
/// A future **Tier-1 proper** scorer would read bindings directly off ``PyDict`` or a flat Fact
/// struct without materializing trees per row — see docs.
#[pyfunction]
pub fn score_rows(
    compiled: &Bound<'_, CompiledRulePackPy>,
    facts: Vec<String>,
) -> PyResult<Vec<String>> {
    let pack = compiled.borrow();
    facts
        .iter()
        .map(|fj| {
            eval_scalar::score_row_json(&pack.inner, fj)
                .map_err(|e| PyValueError::new_err(format!("{e}")))
        })
        .collect()
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

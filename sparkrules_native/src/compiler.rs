//! Tier-1 compilation entry: JSON rulepack → in-memory scorer.
//!
//! Predicate IR (`FieldEq`, …) is intentionally folded into interpreting `ast::Expr` until
//! Tier-2 profiling justifies splitting.

pub use crate::eval_scalar::NativePack;

//! Fact / action cell type for Tier-1 (JSON interop with Python).
//!
//! The guide’s dedicated `Value` enum is deferred: JSON plus `eval_scalar` helpers
//! match `LocalRuleExecutor` for the literal / null cases we round-trip through FFI.

#[allow(dead_code)]
pub type JsonValue = serde_json::Value;

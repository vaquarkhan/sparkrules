//! Rust-side anchors; full statistical parity vs Python runs in ``tests/integration/test_native_parity.py``.

use sparkrules_native::ast::NATIVE_SCHEMA;

#[test]
fn native_schema_matches_python_bundle() {
    assert_eq!(NATIVE_SCHEMA, "1");
}

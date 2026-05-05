//! Action field naming (mirror ``compile_action`` in ``sparkrules.compiler.closure``).

/// Strip ``result.`` prefix (closure compiler contract).
#[inline]
pub fn action_field_name(field_path: &str) -> String {
    match field_path.strip_prefix("result.") {
        Some(s) => s.to_string(),
        None => field_path.to_string(),
    }
}

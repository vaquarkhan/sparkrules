//! Typed errors (mapped to Python exceptions at the FFI boundary).

use thiserror::Error;

#[derive(Debug, Error)]
pub enum NativeError {
    #[error("native JSON: {0}")]
    Json(String),
    #[error("compile: {0}")]
    Compile(String),
    #[error("score: {0}")]
    Score(String),
}

impl From<serde_json::Error> for NativeError {
    fn from(e: serde_json::Error) -> Self {
        NativeError::Json(e.to_string())
    }
}

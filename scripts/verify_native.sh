#!/usr/bin/env bash
# Rust checks for sparkrules_native (run on Linux/macOS CI or dev machines with a linker).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/sparkrules_native"
if ! command -v cargo >/dev/null 2>&1; then
  echo "cargo not found; skip Rust verification (install https://rustup.rs )" >&2
  exit 0
fi
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test

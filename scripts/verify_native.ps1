# Rust checks for sparkrules_native (requires MSVC Build Tools + Rust on Windows).
$ErrorActionPreference = "Stop"
$crate = Join-Path $PSScriptRoot "..\sparkrules_native"
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    Write-Host "cargo not found; install Rust from https://rustup.rs — skipping native verification." -ForegroundColor Yellow
    exit 0
}
Push-Location $crate
try {
    cargo fmt --check
    cargo clippy --all-targets -- -D warnings
    cargo test
} finally {
    Pop-Location
}

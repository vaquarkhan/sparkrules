# Run SparkRules API + Workbench. Default port 8042 (set SPARKRULES_PORT to override).
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not in PATH. Install Python 3.11+ and add to PATH."
}
Write-Host "Installing package (editable)..." -ForegroundColor Cyan
python -m pip install -e "." -q
$port = if ($env:SPARKRULES_PORT) { $env:SPARKRULES_PORT } else { "8042" }
Write-Host ""
Write-Host " SparkRules API" -ForegroundColor Green
Write-Host " Workbench: http://127.0.0.1:$port/workbench/"
Write-Host " Health:    http://127.0.0.1:$port/health"
Write-Host " Leave this window open. Ctrl+C to stop."
Write-Host ""
python -m uvicorn sre.api.app:create_app --factory --host 127.0.0.1 --port $port

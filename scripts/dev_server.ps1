# Run SparkRules API. Uses the same `python` as in PATH; see dev_server.py.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "python not in PATH"
}
$env:SPARKRULES_PORT = if ($env:SPARKRULES_PORT) { $env:SPARKRULES_PORT } else { "8042" }
python -m pip install -e "." -q
python (Join-Path $PSScriptRoot "dev_server.py")

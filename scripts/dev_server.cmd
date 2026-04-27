@echo off
setlocal
cd /d "%~dp0.."
where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: python not in PATH. Install Python 3.11+ and enable "Add to PATH".
  pause
  exit /b 1
)
echo Installing package (editable)...
python -m pip install -e "." -q
if errorlevel 1 (
  echo ERROR: pip install -e . failed. Run this window from the repo you cloned.
  pause
  exit /b 1
)
if "%SPARKRULES_PORT%"=="" set SPARKRULES_PORT=8042
echo.
echo  SparkRules API
echo  Workbench: http://127.0.0.1:%SPARKRULES_PORT%/workbench/
echo  Health:    http://127.0.0.1:%SPARKRULES_PORT%/health
echo  OpenAPI:   http://127.0.0.1:%SPARKRULES_PORT%/docs
echo  Leave this window open. Press Ctrl+C to stop.
echo.
python -m uvicorn sre.api.app:create_app --factory --host 127.0.0.1 --port %SPARKRULES_PORT%
if errorlevel 1 (
  echo.
  echo If you see "No module named sre", run from the repository root: pip install -e .
  pause
)

@echo off
setlocal
cd /d "%~dp0.."
where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: python not in PATH. Install Python 3.11+ from https://www.python.org/downloads/
  echo During setup, check "Add python.exe to PATH".
  pause
  exit /b 1
)
echo [1/2] pip install (editable) ...
python -m pip install -e "." -q
if errorlevel 1 (
  echo ERROR: pip install failed. Open cmd in this folder: %cd%
  pause
  exit /b 1
)
if "%SPARKRULES_PORT%"=="" set SPARKRULES_PORT=8042
echo [2/2] Starting server (port=%SPARKRULES_PORT%) ...
echo.
python "%~dp0dev_server.py"
if errorlevel 1 (
  echo.
  echo If import failed, run:  scripts\check_env.cmd
  pause
)

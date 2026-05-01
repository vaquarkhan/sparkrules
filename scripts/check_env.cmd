@echo off
setlocal
cd /d "%~dp0.."
echo === SparkRules environment check ===
echo Repository: %cd%
if defined SPARKRULES_PORT (
  echo SPARKRULES_PORT=%SPARKRULES_PORT%
) else (
  echo SPARKRULES_PORT not set ^(default in dev_server is 8042^)
)
echo.
where python
python --version
echo.
echo Testing import sparkrules using the same Python shown by "where python" / "python --version" ^(must match dev_server^)...
python -c "import sparkrules, sys; import sparkrules.api.app; print('OK: sparkrules import works'); print('OK: executable =', sys.executable)" 2>&1
if errorlevel 1 (
  echo.
  echo --- FIX: install editable package in THIS environment ---
  echo   python -m pip install -e "."
  echo   If you have multiple Pythons, use the full path to the intended python.
  echo.
) else (
  echo.
  echo Next:  scripts\dev_server.cmd
  echo   Or:   python -m uvicorn sparkrules.api.app:create_app --factory --host 127.0.0.1 --port 8042
  echo   Then: http://127.0.0.1:8042/workbench/   ^(match the port^)
  echo   Browser ERR_CONNECTION_REFUSED = server not running or wrong port / https vs http
)
echo.
pause

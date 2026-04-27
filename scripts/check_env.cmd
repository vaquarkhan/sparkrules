@echo off
setlocal
cd /d "%~dp0.."
echo === SparkRules environment check ===
echo Repository: %cd%
echo.
where python
python --version
echo.
echo Testing import sre...
python -c "import sre; import sre.api.app; print('OK: sre import works')" 2>&1
if errorlevel 1 (
  echo.
  echo FIX: run from this folder:
  echo   python -m pip install -e "."
  echo.
) else (
  echo.
  echo Next: run  scripts\dev_server.cmd
  echo Then open: http://127.0.0.1:8042/workbench/
)
echo.
pause

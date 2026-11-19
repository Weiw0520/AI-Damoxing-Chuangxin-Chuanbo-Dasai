@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Project Python environment was not found.
  exit /b 1
)
".venv\Scripts\python.exe" -c "import playwright.sync_api" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r scripts\requirements-web-acceptance.txt
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -X utf8 scripts\run_b_refine_web_acceptance.py %*
exit /b %errorlevel%

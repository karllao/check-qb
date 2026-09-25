@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m check_qb.cli serve %*
) else (
  python -m check_qb.cli serve %*
)
pause

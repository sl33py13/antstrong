@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m tools.blind_exam %*
) else (
  python -m tools.blind_exam %*
)
echo.
pause

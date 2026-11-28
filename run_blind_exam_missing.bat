@echo off
rem Runs only the exams that did not complete on 28 Nov 2026.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m tools.blind_exam --only gemini_ops,gemini_traps,openai_combined
) else (
  python -m tools.blind_exam --only gemini_ops,gemini_traps,openai_combined
)
echo.
pause

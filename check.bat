@echo off
rem Video Factory Kit - health check (Windows). Double-click this file. Writes check_report.txt.
cd /d "%~dp0"
if exist "tools\venv_render\Scripts\python.exe" (
  "tools\venv_render\Scripts\python.exe" tools\check.py
) else (
  py -3.12 tools\check.py
)
echo.
pause

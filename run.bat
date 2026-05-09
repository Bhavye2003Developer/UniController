@echo off
cd /d "%~dp0"
if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" run.py >> "%~dp0unicontroller.log" 2>&1
) else (
    python run.py >> "%~dp0unicontroller.log" 2>&1
)

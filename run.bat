@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_CMD=python"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sqlite3" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if "%PYTHON_CMD%"=="python" (
  python -c "import sqlite3" >nul 2>nul
  if errorlevel 1 set "PYTHON_CMD="
)
if not defined PYTHON_CMD if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" set PYTHON_CMD="%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not defined PYTHON_CMD (
  echo Python 3.10 or newer is required. Install it from https://www.python.org/downloads/ and run this file again.
  pause
  exit /b 1
)
%PYTHON_CMD% app.py
if errorlevel 1 (
  echo.
  echo The app stopped. Check the error above. First launch needs internet to download the Hugging Face dataset.
  pause
)

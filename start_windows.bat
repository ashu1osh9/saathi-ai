@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Python 3.10 or newer is required. Install it from python.org and run this script again.
    pause
    exit /b 1
  )
)
if not exist .env (
  copy .env.example .env >nul
  echo.
  echo FIRST RUN: Edit .env and add GNANI_API_KEY before testing voice.
  notepad .env
)
.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.lock
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8000 in Chrome.
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
pause

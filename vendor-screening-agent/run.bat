@echo off
title Vendor Screening Agent
cd /d "%~dp0"

echo ============================================================
echo   VENDOR SCREENING AGENT - starting up
echo ============================================================
echo.

REM --- find Python (py or python) ---
set "PY="
where py >nul 2>nul && set "PY=py"
if "%PY%"=="" ( where python >nul 2>nul && set "PY=python" )

if "%PY%"=="" (
  echo  [X] Python is NOT installed on this computer.
  echo.
  echo  Please do this once:
  echo    1^) Open https://www.python.org/downloads/
  echo    2^) Click "Download Python", run the installer
  echo    3^) IMPORTANT: tick the box  "Add Python to PATH"  then Install
  echo    4^) Double-click this run.bat again
  echo.
  pause
  exit /b
)

echo  [1/2] Installing what the app needs (first time only, 1-2 minutes)...
%PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt

echo  [2/2] Starting the app...
start "Vendor Screening Agent - SERVER (keep open)" cmd /k "%PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo  Opening your browser in a few seconds...
timeout /t 6 >nul
start "" http://127.0.0.1:8000

echo.
echo ============================================================
echo   The app is running at:  http://127.0.0.1:8000
echo   If the page shows an error, wait 5 seconds and refresh.
echo   To STOP: close the black "SERVER" window that opened.
echo ============================================================
echo.
pause

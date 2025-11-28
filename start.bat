@echo off
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

REM Root-relative paths
set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%ui"

REM Adjust these if you use python3/npm aliases
set "PYTHON=python"
set "NPM=npm"

REM Ensure backend deps (uvicorn etc.) are available
cd /d %BACKEND%
%PYTHON% -m pip show uvicorn >NUL 2>&1
if errorlevel 1 (
  echo Installing backend dependencies...
  %PYTHON% -m pip install -r requirements.txt --user
)

REM Start FastAPI backend
start "EventLink API" cmd /k "cd /d %BACKEND% && %PYTHON% -m uvicorn main:app --reload --port 8000"

REM Start Angular frontend
start "EventLink UI" cmd /k "cd /d %FRONTEND% && %NPM% install && %NPM% start"

echo Launching EventLink backend (http://localhost:8000) and frontend (http://localhost:4200)...
echo If a window closes immediately, check that Python and npm are on PATH.
pause

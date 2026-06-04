@echo off
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"

for /f "usebackq delims=" %%R in (`powershell -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT_DIR%resolve_root_windows.ps1" -ScriptDir "%SCRIPT_DIR%"`) do set "ROOT=%%R"

REM Prefer backend folder that contains this launcher.
for %%I in ("%SCRIPT_DIR%..") do set "BACKEND_DIR=%%~fI"

if not exist "%BACKEND_DIR%\app\main.py" (
  set "BACKEND_DIR="
  for /d /r "%ROOT%" %%D in (*) do (
    if exist "%%D\app\main.py" (
      echo %%D | findstr /I "optimize MK-APIS-backend MK-AIPS-CPP-Inference-bnd-main" >nul
      if not errorlevel 1 (
        set "BACKEND_DIR=%%D"
        goto found_backend
      )
    )
  )
  for /d /r "%ROOT%" %%D in (*) do (
    if exist "%%D\app\main.py" (
      set "BACKEND_DIR=%%D"
      goto found_backend
    )
  )
)

:found_backend
if "%BACKEND_DIR%"=="" (
  echo Cannot find backend folder with app\main.py under %ROOT%
  pause
  exit /b 1
)

cd /d "%BACKEND_DIR%"
echo Root folder: %ROOT%
echo Backend folder: %BACKEND_DIR%
echo Model folder: %BACKEND_DIR%\models

set "AIPS_MODEL_DIR=%BACKEND_DIR%\models"
if exist "venv\Scripts\activate.bat" call "venv\Scripts\activate.bat"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8999
pause

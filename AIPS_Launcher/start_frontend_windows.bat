@echo off
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"

for /f "usebackq delims=" %%R in (`powershell -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT_DIR%resolve_root_windows.ps1" -ScriptDir "%SCRIPT_DIR%"`) do set "ROOT=%%R"

set "FRONTEND_DIR="
for /d /r "%ROOT%" %%D in (*) do (
  if exist "%%D\package.json" (
    if exist "%%D\src\App.jsx" (
      echo %%D | findstr /I "fnd frontend" >nul
      if not errorlevel 1 (
        set "FRONTEND_DIR=%%D"
        goto found_frontend
      )
    )
  )
)

:found_frontend
if "%FRONTEND_DIR%"=="" (
  echo Cannot find frontend folder with package.json and src\App.jsx under %ROOT%
  pause
  exit /b 1
)

cd /d "%FRONTEND_DIR%"
echo Root folder: %ROOT%
echo Frontend folder: %FRONTEND_DIR%
npm run dev -- --host 0.0.0.0 --port 5074
pause

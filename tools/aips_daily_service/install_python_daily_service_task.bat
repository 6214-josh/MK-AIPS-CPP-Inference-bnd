@echo off
setlocal EnableExtensions

REM 安裝 Python 固定服務：
REM 登入後啟動 aips_daily_update_service.py
REM Python service 每天 00:00 與 12:00 執行 run_aips_today_14cnc.bat /silent

set "TASK_NAME=AIPS_PY_DAILY_0000_1200_SERVICE"
set "SCRIPT_PATH=%~dp0aips_daily_update_service.py"

if not exist "%SCRIPT_PATH%" (
  echo 找不到 Python service：
  echo %SCRIPT_PATH%
  pause
  exit /b 1
)

where pythonw >nul 2>nul
if not errorlevel 1 (
  for /f "delims=" %%P in ('where pythonw') do (
    set "PYTHON_EXE=%%P"
    goto :FOUND_PY
  )
)

where python >nul 2>nul
if not errorlevel 1 (
  for /f "delims=" %%P in ('where python') do (
    set "PYTHON_EXE=%%P"
    goto :FOUND_PY
  )
)

echo 找不到 python / pythonw，請先安裝 Python 或把 Python 加入 PATH。
pause
exit /b 1

:FOUND_PY
echo 使用 Python：
echo %PYTHON_EXE%
echo.
schtasks /Create /F /TN "%TASK_NAME%" /SC ONLOGON /TR "\"%PYTHON_EXE%\" \"%SCRIPT_PATH%\""

echo.
echo 完成。可手動先執行：
echo python "%SCRIPT_PATH%"
echo.
pause

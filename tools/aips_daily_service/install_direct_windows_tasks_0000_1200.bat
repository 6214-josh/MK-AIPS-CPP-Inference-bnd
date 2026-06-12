@echo off
setlocal EnableExtensions

REM 直接建立兩個 Windows 工作排程：
REM 每天 00:00 與 12:00 直接執行 run_aips_today_14cnc.bat /silent

set "BAT_PATH=%~dp0run_aips_today_14cnc.bat"

if not exist "%BAT_PATH%" (
  echo 找不到：
  echo %BAT_PATH%
  pause
  exit /b 1
)

schtasks /Create /F /TN "AIPS_14CNC_DAILY_0000" /SC DAILY /ST 00:00 /TR "\"%BAT_PATH%\" /silent"
schtasks /Create /F /TN "AIPS_14CNC_DAILY_1200" /SC DAILY /ST 12:00 /TR "\"%BAT_PATH%\" /silent"

echo.
echo 已建立：
echo AIPS_14CNC_DAILY_0000
echo AIPS_14CNC_DAILY_1200
echo.
pause

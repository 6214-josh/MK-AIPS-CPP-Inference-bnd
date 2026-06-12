@echo off
setlocal
schtasks /Delete /F /TN "AIPS_PY_DAILY_0000_1200_SERVICE"
schtasks /Delete /F /TN "AIPS_14CNC_DAILY_0000"
schtasks /Delete /F /TN "AIPS_14CNC_DAILY_1200"
echo.
echo 已嘗試刪除 AIPS 相關工作排程。
pause

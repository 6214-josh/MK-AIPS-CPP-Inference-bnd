@echo off
set "SCRIPT_DIR=%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT_DIR%create_desktop_shortcuts_windows.ps1"
pause

@echo off
REM Double-click to stop starting the servers at logon.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall-autostart.ps1" %*
echo.
pause

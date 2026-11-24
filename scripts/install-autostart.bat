@echo off
REM Double-click to register both servers to start at logon.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-autostart.ps1" %*
echo.
pause

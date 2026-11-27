@echo off
REM Double-click to restart the Flask backend (sau_backend.py, port 5409).
setlocal
chcp 65001 > nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart-backend-of-social-auto-upload.ps1" %*
echo.
pause

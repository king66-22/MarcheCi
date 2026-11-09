@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0marcheci.ps1" status
set "RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RESULT%

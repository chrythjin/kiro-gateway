@echo off
title Kiro Gateway Server
:: Change directory to the parent folder of this batch file (repo root)
cd /d "%~dp0.."
echo ===================================================
echo   Starting Kiro Gateway Server in Foreground...
echo   Environment: Python 3.13
echo   Host: http://0.0.0.0:8000
echo ===================================================
echo.
py main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Kiro Gateway exited with code %ERRORLEVEL%.
    pause
)

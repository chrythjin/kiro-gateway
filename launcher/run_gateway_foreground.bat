@echo off
title Kiro Gateway Server
cd /d "%~dp0.."
echo ===================================================
echo   Starting Kiro Gateway Server in Foreground...
echo   Environment: Python 3.13
echo   Host: http://0.0.0.0:8888
echo ===================================================
echo.
py main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Kiro Gateway exited with code %ERRORLEVEL%.
    pause
)

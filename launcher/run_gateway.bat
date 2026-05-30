@echo off
cd /d "%~dp0"
start "" wscript.exe "%~dp0run_gateway.vbs"
exit /b 0

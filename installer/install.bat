@echo off
title Kiro Gateway Auto Installer
color 0B
cd /d "%~dp0"

echo ========================================================
echo   Kiro Gateway Auto Installer (Windows)
echo ========================================================
echo.

:: Step 1: Check if Python launcher (py) or python is installed
echo [1/3] Checking Python Environment...
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [+] Python Launcher (py) detected successfully!
    set PYTHON_CMD=py
) else (
    where python >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo [+] Python detected successfully!
        set PYTHON_CMD=python
    ) else (
        echo [ERROR] Python is not installed or not added to your PATH environment variable.
        echo Please download and install Python (v3.10 or higher) from https://www.python.org/
        echo.
        echo [NOTE] Make sure to check the "Add Python to PATH" option during installation.
        echo.
        pause
        exit /b 1
    )
)

:: Step 2: Install required library dependencies
echo.
echo [2/3] Installing Package Dependencies from requirements.txt...
echo Running: %PYTHON_CMD% -m pip install -r ..\requirements.txt
echo Please wait, this may take a few moments...
echo.

%PYTHON_CMD% -m pip install --upgrade pip
%PYTHON_CMD% -m pip install -r ..\requirements.txt

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Dependency installation failed. Please check your network connection or Python setup.
    pause
    exit /b 1
)
echo.
echo [+] Dependencies installed successfully!

:: Step 3: Configure Environment Variables (.env)
echo.
echo [3/3] Setting up Environment Configuration (.env)...
if not exist "..\.env" (
    if exist "..\.env.example" (
        copy "..\.env.example" "..\.env" >nul
        echo [+] Created a new '.env' configuration file from template (.env.example).
        echo [!] IMPORTANT: Please open and edit '.env' in the parent directory to add your PROXY_API_KEY.
    ) else (
        echo [WARNING] .env.example was not found in parent directory. Could not generate .env file.
    )
) else (
    echo [+] Existing '.env' configuration file detected. Skipping creation to preserve your settings.
)

echo.
echo ========================================================
echo   Installation Completed Successfully!
echo ========================================================
echo.
echo To start the server, please use one of these scripts in the parent folder:
echo.
echo  1. run_gateway_foreground.bat (Recommended for first run, shows logs)
echo  2. run_gateway.bat            (Runs in hidden background mode)
echo.
pause

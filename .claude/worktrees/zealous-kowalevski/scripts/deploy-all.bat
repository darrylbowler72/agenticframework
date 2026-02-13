@echo off
REM Windows batch script for deployment
REM This calls the bash scripts using Git Bash or WSL

echo ================================================
echo DevOps Agentic Framework - Complete Deployment
echo ================================================
echo.

echo Checking for bash environment...

REM Check for Git Bash
where bash >nul 2>nul
if %ERRORLEVEL% == 0 (
    echo Found bash, using Git Bash
    bash scripts/deploy-all.sh
    exit /b
)

REM Check for WSL
where wsl >nul 2>nul
if %ERRORLEVEL% == 0 (
    echo Found WSL, using WSL bash
    wsl bash scripts/deploy-all.sh
    exit /b
)

echo.
echo ERROR: Bash environment not found!
echo.
echo Please install one of the following:
echo   1. Git for Windows (includes Git Bash): https://git-scm.com/download/win
echo   2. WSL (Windows Subsystem for Linux): wsl --install
echo.
echo After installation, run this script again.
pause

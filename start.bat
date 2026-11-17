@echo off
title Minecraft 4-Letter Username Checker

echo ============================================
echo   Minecraft 4-Letter Username Checker
echo ============================================
echo.

where python >nul 2>&1

if %errorlevel% neq 0 (
    echo Python is not installed.
    echo.
    echo Install Python from:
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b
)

echo Installing required package...
python -m pip install requests

echo.
echo Starting checker...
echo.

python checker.py

echo.
echo ============================================
echo Checker stopped.
echo ============================================
pause
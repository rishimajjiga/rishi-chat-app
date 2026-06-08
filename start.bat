@echo off
REM ── RealChat Quick Start (Windows) ─────────────────────────────────────────
title RealChat Setup
color 0A

echo.
echo  ^>^> RealChat Quick Start
echo.

REM 1. Python check
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found
for /f "tokens=*" %%i in ('python --version') do echo     %%i

REM 2. Virtual environment
if not exist "venv\" (
    echo [..] Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
echo [OK] Virtual environment active

REM 3. Dependencies
echo [..] Installing dependencies...
pip install -q -r requirements.txt
echo [OK] Dependencies installed

REM 4. .env setup
if not exist ".env" (
    copy .env.example .env >nul
    echo [OK] Created .env from template
)

REM 5. Launch
echo.
echo  Server starting at http://localhost:5000
echo  Press Ctrl+C to stop
echo.
python app.py

pause

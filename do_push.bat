@echo off
cd /d "%~dp0"
echo.
echo === Pushing Rishi Chat App to GitHub ===
echo.

git --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git not found. Install from https://git-scm.com
    pause & exit /b 1
)

if not exist ".git" (
    git init
    git branch -M main
    echo [OK] Git initialized
) else (
    echo [OK] Git repo exists
)

git config user.email "rishimajjiga291@gmail.com"
git config user.name "Rishi Majjiga"

if not exist "uploads" mkdir uploads
if not exist "uploads\.gitkeep" type nul > uploads\.gitkeep

git add .
git status --short

git commit -m "Rishi - Pure Privacy Messaging app" 2>nul || echo [OK] Nothing new to commit

git remote remove origin 2>nul
git remote add origin https://github.com/rishimajjiga/rishi-chat-app.git

echo.
echo Pushing to https://github.com/rishimajjiga/rishi-chat-app ...
echo (A browser window may open asking you to sign in to GitHub)
echo.
git push -u origin main

echo.
echo === Done! ===
echo GitHub repo: https://github.com/rishimajjiga/rishi-chat-app
echo.
pause

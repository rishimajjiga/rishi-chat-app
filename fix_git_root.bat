@echo off
cd /d "%~dp0"
echo === Fixing git repo root ===
echo Current dir: %CD%
echo.

REM Remove the bad .git folder and start fresh
rmdir /s /q ".git"
echo [OK] Removed old .git

REM Init fresh git repo RIGHT HERE in chatapp folder
git init
git branch -M main
git config user.email "rishimajjiga291@gmail.com"
git config user.name "Rishi Majjiga"
echo [OK] Fresh git init in chatapp folder

REM Stage all project files
git add .
git status --short

REM Commit
git commit -m "Rishi Chat App - initial commit (fixed repo root)"

REM Set remote and force push
git remote add origin https://github.com/rishimajjiga/rishi-chat-app.git
git push -u origin main --force

echo.
echo === Done! Files are now at repo root ===
echo Check: https://github.com/rishimajjiga/rishi-chat-app
pause

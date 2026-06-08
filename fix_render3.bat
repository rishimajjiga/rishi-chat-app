@echo off
cd /d "%~dp0"
git add Dockerfile
git commit -m "Add working Dockerfile for Render deployment"
git push origin main
echo.
echo === Done! ===
pause

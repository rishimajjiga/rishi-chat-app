@echo off
cd /d "%~dp0"
echo === Fixing Render deployment ===

REM Remove docker-compose.yml so Render uses render.yaml instead
if exist "docker-compose.yml" del "docker-compose.yml"
echo [OK] Removed docker-compose.yml

REM Stage and commit the fixes
git add render.yaml
git rm --cached docker-compose.yml 2>nul
git add -u
git commit -m "Fix: use env:python in render.yaml, remove docker-compose"

git push origin main
echo.
echo === Done! Render will auto-redeploy now ===
echo.
pause

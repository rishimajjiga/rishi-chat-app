@echo off
cd /d "%~dp0"
echo === Removing Dockerfile so Render uses render.yaml ===

if exist "Dockerfile" del "Dockerfile"
echo [OK] Removed Dockerfile

git rm --cached Dockerfile 2>nul
git add -u
git commit -m "Remove Dockerfile so Render uses render.yaml (Python env)"

git push origin main
echo.
echo === Done! Render will redeploy with Python runtime now ===
pause

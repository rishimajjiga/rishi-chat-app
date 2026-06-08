# Rishi Chat App - Push to GitHub
# Run this script once to create the GitHub repo and push all files.
# Right-click this file -> "Run with PowerShell"

$ErrorActionPreference = "Stop"
$RepoName = "rishi-chatting-app"
$AppDir   = $PSScriptRoot

Write-Host ""
Write-Host "=== Rishi Chat App - GitHub Setup ===" -ForegroundColor Green
Write-Host ""

# Check git
try { git --version | Out-Null } catch {
    Write-Host "ERROR: Git is not installed." -ForegroundColor Red
    Write-Host "Download from https://git-scm.com/download/win then re-run this script."
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] Git found" -ForegroundColor Green

Set-Location $AppDir

# Init repo if needed
if (-not (Test-Path ".git")) {
    git init
    git branch -M main
    Write-Host "[OK] Git repository initialized" -ForegroundColor Green
} else {
    Write-Host "[OK] Git repository already exists" -ForegroundColor Green
}

# Configure user if not set
$gitEmail = git config user.email 2>$null
if (-not $gitEmail) {
    git config user.email "rishimajjiga291@gmail.com"
    git config user.name  "Rishi"
}

# Create uploads/.gitkeep so the folder is tracked
if (-not (Test-Path "uploads")) { New-Item -ItemType Directory -Path "uploads" | Out-Null }
if (-not (Test-Path "uploads\.gitkeep")) { New-Item -ItemType File -Path "uploads\.gitkeep" | Out-Null }

# Stage and commit
git add .
$status = git status --short
if ($status) {
    git commit -m "Initial commit - Rishi Pure Privacy Messaging"
    Write-Host "[OK] Files committed" -ForegroundColor Green
} else {
    Write-Host "[OK] Nothing new to commit" -ForegroundColor Green
}

# Check for GitHub CLI
$ghAvailable = $false
try { gh --version | Out-Null; $ghAvailable = $true } catch {}

if ($ghAvailable) {
    Write-Host ""
    Write-Host "GitHub CLI detected. Creating repo..." -ForegroundColor Cyan

    # Check if already logged in
    $loginStatus = gh auth status 2>&1
    if ($loginStatus -match "not logged") {
        Write-Host "Please log in to GitHub:"
        gh auth login
    }

    # Create repo (ignore error if already exists)
    gh repo create $RepoName --public --description "Pure Privacy Messaging - messages auto-delete after 1hr" 2>$null
    $remote = "https://github.com/$(gh api user --jq .login)/$RepoName.git"

    if (-not (git remote get-url origin 2>$null)) {
        git remote add origin $remote
    } else {
        git remote set-url origin $remote
    }

    git push -u origin main
    Write-Host ""
    Write-Host "SUCCESS!" -ForegroundColor Green
    $username = gh api user --jq .login
    Write-Host "GitHub repo : https://github.com/$username/$RepoName" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "=== For a LIVE working URL ===" -ForegroundColor Yellow
    Write-Host "GitHub Pages cannot run Python. Use Render.com (free):" -ForegroundColor Yellow
    Write-Host "1. Go to https://render.com"
    Write-Host "2. New > Web Service > Connect GitHub"
    Write-Host "3. Select '$RepoName'"
    Write-Host "4. Click Deploy"
    Write-Host "=> Live URL: https://$RepoName.onrender.com"

} else {
    Write-Host ""
    Write-Host "GitHub CLI not found. Follow these steps:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "STEP 1 - Create repo on GitHub:" -ForegroundColor Cyan
    Write-Host "  Go to https://github.com/new"
    Write-Host "  Repository name: $RepoName"
    Write-Host "  Visibility: Public"
    Write-Host "  Click 'Create repository'"
    Write-Host ""
    Write-Host "STEP 2 - Copy the HTTPS URL shown on GitHub (looks like:" -ForegroundColor Cyan
    Write-Host "  https://github.com/YOUR_USERNAME/$RepoName.git)"
    Write-Host ""
    $remote = Read-Host "Paste your GitHub repo URL here"
    $remote = $remote.Trim()

    if ($remote) {
        if (-not (git remote get-url origin 2>$null)) {
            git remote add origin $remote
        } else {
            git remote set-url origin $remote
        }
        git push -u origin main
        Write-Host ""
        Write-Host "SUCCESS! Code pushed to GitHub." -ForegroundColor Green
        Write-Host ""
        Write-Host "=== For a LIVE working URL ===" -ForegroundColor Yellow
        Write-Host "GitHub Pages cannot run Python backends."
        Write-Host "For a free live URL use Render.com:"
        Write-Host "  1. Go to https://render.com"
        Write-Host "  2. New > Web Service > Connect GitHub"
        Write-Host "  3. Select '$RepoName' > Deploy"
        Write-Host "  => Your live URL will be: https://$RepoName.onrender.com"
    }
}

Write-Host ""
Read-Host "Press Enter to close"

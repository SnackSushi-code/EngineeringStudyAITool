$ErrorActionPreference = 'Stop'

Write-Host 'Ann-E Phase 0 repository bootstrap' -ForegroundColor Cyan

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  throw 'Git is not installed or is not on PATH. Install Git and rerun this script.'
}

if (-not (Test-Path '.git')) {
  git init
}

git branch -M main

git add .
git commit -m 'chore: establish Ann-E phase 0 foundation'

$remote = git remote get-url origin 2>$null
if (-not $remote) {
  git remote add origin 'https://github.com/SnackSushi-code/EngineeringStudyAITool.git'
}

Write-Host ''
Write-Host 'Local Phase 0 foundation is committed.' -ForegroundColor Green
Write-Host 'Next: authenticate with GitHub, then run:' -ForegroundColor Yellow
Write-Host '  git push -u origin main'

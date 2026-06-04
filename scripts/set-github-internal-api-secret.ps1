#Requires -Version 5.1
<#
.SYNOPSIS
  Set GitHub Actions secret INTERNAL_API_SECRET from Railway (must match production).

  Requires: gh CLI logged in (gh auth login) and RAILWAY_TOKEN.
#>
param(
    [string] $Repo = "cesarbohjr/gravitre-saas-backend",
    [string] $Service = "gravitre-saas-backend"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "Install GitHub CLI: https://cli.github.com/" -ForegroundColor Red
    exit 1
}

$auth = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Run: gh auth login" -ForegroundColor Yellow
    Write-Host $auth
    exit 1
}

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Host "Install Railway CLI: npm i -g @railway/cli" -ForegroundColor Red
    exit 1
}

$envFile = Join-Path (Split-Path -Parent $PSScriptRoot) "backend\.env.operator.local"
if (-not $env:RAILWAY_TOKEN -and (Test-Path $envFile)) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^RAILWAY_TOKEN=(.+)$') { $env:RAILWAY_TOKEN = $matches[1].Trim().Trim('"') }
    }
}
if (-not $env:RAILWAY_TOKEN) {
    Write-Host "Set RAILWAY_TOKEN (project token) in env or backend/.env.operator.local" -ForegroundColor Red
    exit 1
}

$json = railway variables --service $Service --json 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or -not $json.Trim()) {
    Write-Host "Failed to read Railway variables" -ForegroundColor Red
    exit 1
}
$vars = $json | ConvertFrom-Json
$secret = $vars.INTERNAL_API_SECRET
if (-not $secret) {
    Write-Host "INTERNAL_API_SECRET not set on Railway service '$Service'" -ForegroundColor Red
    exit 1
}

Write-Host "Setting INTERNAL_API_SECRET on $Repo (from Railway)..."
$secret | gh secret set INTERNAL_API_SECRET --repo $Repo
if ($LASTEXITCODE -ne 0) {
    Write-Host "gh secret set failed" -ForegroundColor Red
    exit 1
}

Write-Host "Done. Verify: gh secret list --repo $Repo" -ForegroundColor Green

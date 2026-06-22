#Requires -Version 5.1
<#
.SYNOPSIS
  Apply gravitre.app / api.gravitre.app auth and API env via CLI (Supabase, Railway, Vercel).

  Does NOT update vendor OAuth consoles (Google Cloud, HubSpot, etc.) - see output checklist.
#>
param(
    [switch] $SkipDeploy,
    [string] $AppUrl = "https://gravitre.app",
    [string] $ApiUrl = "https://api.gravitre.app",
    [string] $RailwayService = "gravitre-saas-backend"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

function Import-RailwayToken {
    if ($env:RAILWAY_TOKEN) { return }
    if (-not (Test-Path $OperatorFile)) { return }
    Get-Content $OperatorFile | ForEach-Object {
        if ($_ -match '^RAILWAY_TOKEN=(.+)$') {
            $env:RAILWAY_TOKEN = $matches[1].Trim().Trim('"')
        }
    }
}

Write-Host ""
Write-Host "=== 1/4 Supabase auth URLs ===" -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\sync-supabase-auth-urls.ps1") -AppUrl $AppUrl
if ($LASTEXITCODE -ne 0) { throw "sync-supabase-auth-urls failed" }

Write-Host ""
Write-Host "=== 2/4 Supabase Google provider ===" -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\configure-supabase-google.ps1")
if ($LASTEXITCODE -ne 0) { throw "configure-supabase-google failed" }

Write-Host ""
Write-Host "=== 3/4 Railway env ===" -ForegroundColor Cyan
Import-RailwayToken
if (-not $env:RAILWAY_TOKEN) {
    Write-Host "RAILWAY_TOKEN missing - skip Railway (add to backend/.env.operator.local)." -ForegroundColor Yellow
} else {
    railway variable set `
        "NEXT_PUBLIC_APP_URL=$AppUrl" `
        "PUBLIC_APP_URL=$AppUrl" `
        "API_PUBLIC_URL=$ApiUrl" `
        --service $RailwayService 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "railway variable set failed" }
    Write-Host "Railway env updated." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== 4/4 Vercel production env ===" -ForegroundColor Cyan
Push-Location $RepoRoot
try {
    $ApiUrl | vercel env add FASTAPI_BASE_URL production --force 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "vercel FASTAPI_BASE_URL failed" }
    $AppUrl | vercel env add NEXT_PUBLIC_APP_URL production --force 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "vercel NEXT_PUBLIC_APP_URL failed" }

    if (-not $SkipDeploy) {
        Write-Host "Deploying Vercel production..." -ForegroundColor Cyan
        vercel deploy --prod --yes 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "vercel deploy failed" }
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "=== OAuth status (backend redirect URIs) ===" -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\check-all-oauth-status.ps1") -ApiBase $ApiUrl

Write-Host ""
Write-Host "CLI apply complete." -ForegroundColor Green

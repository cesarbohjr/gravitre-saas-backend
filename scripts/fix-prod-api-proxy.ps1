#Requires -Version 5.1
<#
.SYNOPSIS
  Fix production API proxy: point Vercel FASTAPI_BASE_URL at Railway and redeploy.

.DESCRIPTION
  api.gravitre.app is not wired to Railway yet. Until DNS is configured, the web app
  must proxy /api/* to the live Railway backend host.
#>
param(
    [switch] $SkipDeploy
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendUrl = "https://gravitre-saas-backend-production.up.railway.app"
$AppUrl = "https://gravitre.app"

Write-Host "Updating Vercel production env..." -ForegroundColor Cyan
Push-Location $RepoRoot
try {
    $BackendUrl | vercel env add FASTAPI_BASE_URL production --force 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "vercel env add FASTAPI_BASE_URL failed" }
    $AppUrl | vercel env add NEXT_PUBLIC_APP_URL production --force 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "vercel env add NEXT_PUBLIC_APP_URL failed" }

    if (-not $SkipDeploy) {
        Write-Host "Deploying production..." -ForegroundColor Cyan
        vercel deploy --prod --yes 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "vercel deploy failed" }
    }
} finally {
    Pop-Location
}

Write-Host "Checking gravitre.app/api health..." -ForegroundColor Cyan
$health = curl.exe -s -w "`nHTTP:%{http_code}" "https://gravitre.app/api/health" 2>&1
Write-Host $health
if ($health -notmatch "HTTP:200") {
    Write-Host "Health check did not return 200 yet. Wait for deploy propagation." -ForegroundColor Yellow
    exit 1
}

Write-Host "Production API proxy restored." -ForegroundColor Green

#Requires -Version 5.1
<#
.SYNOPSIS
  STA-270: enable CoordinationLayer prototype on Railway (internal test org only).

.DESCRIPTION
  Sets COORDINATION_LAYER_ENABLED=true and restricts allowlist to the synthetic smoke org.
  Safe for production: code gates behavior to allowlisted org IDs only.

.PARAMETER Disable
  Turn the flag off (revert to 2A paths for all orgs).

.EXAMPLE
  .\scripts\apply-railway-coordination-layer.ps1
  .\scripts\apply-railway-coordination-layer.ps1 -Disable
#>
param(
    [switch] $Disable,
    [string] $Service = "gravitre-saas-backend",
    [string] $AllowedOrgIds = "00000000-0000-0000-0000-000000000001",
    [string] $EnvFile = $(Join-Path (Split-Path -Parent $PSScriptRoot) "backend\.env.operator.local")
)

$ErrorActionPreference = "Stop"

if (-not $env:RAILWAY_TOKEN -and (Test-Path $EnvFile)) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim().Trim('"')
        if ($key -eq "RAILWAY_TOKEN" -and $val) { $env:RAILWAY_TOKEN = $val }
    }
}

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Host "Install Railway CLI: npm i -g @railway/cli" -ForegroundColor Red
    exit 1
}
if (-not $env:RAILWAY_TOKEN) {
    Write-Host "RAILWAY_TOKEN is not set. Add to backend/.env.operator.local or run railway login." -ForegroundColor Yellow
    exit 1
}

if ($Disable) {
    Write-Host "Disabling CoordinationLayer on Railway service $Service ..."
    railway variables set "COORDINATION_LAYER_ENABLED=false" --service $Service
} else {
    Write-Host "Enabling CoordinationLayer (test org only) on Railway service $Service ..."
    railway variables set "COORDINATION_LAYER_ENABLED=true" --service $Service
    if ($LASTEXITCODE -ne 0) {
        Write-Error "railway variables set COORDINATION_LAYER_ENABLED failed (exit $LASTEXITCODE)"
    }
    railway variables set "COORDINATION_LAYER_ALLOWED_ORG_IDS=$AllowedOrgIds" --service $Service
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "railway variables set failed (exit $LASTEXITCODE)"
}

Write-Host "Triggering Railway redeploy for $Service ..."
railway redeploy --service $Service --yes
if ($LASTEXITCODE -ne 0) {
    Write-Warning "railway redeploy failed (exit $LASTEXITCODE); env vars set - redeploy manually if needed."
}

Write-Host 'Done. After deploy: npm run smoke:sta270-coordination-layer:report -- --expect-enabled'

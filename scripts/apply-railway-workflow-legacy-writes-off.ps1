#Requires -Version 5.1
<#
.SYNOPSIS
  STA-271 C.6: disable legacy workflow writes on Railway after stabilization window.

.DESCRIPTION
  Sets WORKFLOW_LEGACY_WRITES=false on the backend service. Run only after ~2 weeks of
  stable dual-write in production (target: 2026-07-05).

.PARAMETER Force
  Skip the stabilization date guard.

.EXAMPLE
  .\scripts\apply-railway-workflow-legacy-writes-off.ps1
  .\scripts\apply-railway-workflow-legacy-writes-off.ps1 -Force
#>
param(
    [switch] $Force,
    [string] $Service = "gravitre-saas-backend",
    [datetime] $EarliestDate = [datetime]"2026-07-05",
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

if (-not $Force -and (Get-Date) -lt $EarliestDate) {
    Write-Host "C.6 guard: wait until $EarliestDate (or pass -Force). WORKFLOW_LEGACY_WRITES left unchanged."
    exit 0
}

Write-Host "Setting WORKFLOW_LEGACY_WRITES=false on Railway service $Service ..."
railway variables set "WORKFLOW_LEGACY_WRITES=false" --service $Service
if ($LASTEXITCODE -ne 0) {
    Write-Error "railway variables set failed (exit $LASTEXITCODE)"
}

Write-Host "Triggering Railway redeploy for $Service ..."
railway redeploy --service $Service --yes
if ($LASTEXITCODE -ne 0) {
    Write-Warning "railway redeploy failed (exit $LASTEXITCODE); env vars set - redeploy manually if needed."
}

Write-Host "Done. Post-cutover: npm run smoke:sta271-dual-write:report && npm run smoke:swarm-council-lifecycle:report"

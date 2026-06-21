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
    [datetime] $EarliestDate = [datetime]"2026-07-05"
)

$ErrorActionPreference = "Stop"
if (-not $Force -and (Get-Date) -lt $EarliestDate) {
    Write-Host "C.6 guard: wait until $EarliestDate (or pass -Force). WORKFLOW_LEGACY_WRITES left unchanged."
    exit 0
}

Write-Host "Setting WORKFLOW_LEGACY_WRITES=false on Railway service $Service ..."
railway variables set "WORKFLOW_LEGACY_WRITES=false" --service $Service
if ($LASTEXITCODE -ne 0) {
    Write-Error "railway variables set failed (exit $LASTEXITCODE)"
}
Write-Host "Done. Redeploy backend and smoke-test workflow create + execute before closing STA-271."

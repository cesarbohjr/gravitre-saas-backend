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
    [string] $AllowedOrgIds = "00000000-0000-0000-0000-000000000001"
)

$ErrorActionPreference = "Stop"

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

Write-Host "Done. Railway will redeploy; then run: npm run smoke:sta270-coordination-layer:report"

#Requires -Version 5.1
<#
.SYNOPSIS
  Merge NetSuite OAuth credentials into backend/.env.operator.local and push to Railway.
#>
param(
    [string] $ClientId = $env:NETSUITE_CLIENT_ID,
    [string] $ClientSecret = $env:NETSUITE_CLIENT_SECRET,
    [switch] $SkipRailway
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not $ClientId -or -not $ClientSecret) {
    Write-Host "NetSuite OAuth credentials required." -ForegroundColor Yellow
    Write-Host "1. NetSuite Setup -> Integration -> Manage Integrations -> New (OAuth 2.0)" -ForegroundColor Yellow
    Write-Host "2. Redirect URI:" -ForegroundColor Yellow
    Write-Host "   https://api.gravitre.app/api/connectors/oauth/netsuite/callback" -ForegroundColor White
    Write-Host "3. Run:" -ForegroundColor Yellow
    Write-Host '   $env:NETSUITE_CLIENT_ID="<id>"; $env:NETSUITE_CLIENT_SECRET="<secret>"; npm run netsuite:fill-env' -ForegroundColor White
    exit 1
}

& (Join-Path $RepoRoot "scripts\init-operator-platform.ps1") | Out-Null

$lines = Get-Content $OperatorFile
function Set-EnvLine([string]$Key, [string]$Value) {
    $script:lines = $script:lines | Where-Object {
        $t = $_.Trim()
        -not ($t -and -not $t.StartsWith("#") -and $t.StartsWith("$Key="))
    }
    $script:lines += "$Key=$Value"
}

Set-EnvLine "NETSUITE_CLIENT_ID" $ClientId
Set-EnvLine "NETSUITE_CLIENT_SECRET" $ClientSecret
$lines | Set-Content $OperatorFile -Encoding utf8

Write-Host "Updated $OperatorFile with NetSuite credentials" -ForegroundColor Green
if (-not $SkipRailway) {
    & (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")
}

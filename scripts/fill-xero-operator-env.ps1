#Requires -Version 5.1
<#
.SYNOPSIS
  Merge Xero OAuth credentials into backend/.env.operator.local and push to Railway.
#>
param(
    [string] $ClientId = $env:XERO_CLIENT_ID,
    [string] $ClientSecret = $env:XERO_CLIENT_SECRET,
    [switch] $SkipRailway
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not $ClientId -or -not $ClientSecret) {
    Write-Host "Xero OAuth credentials required." -ForegroundColor Yellow
    Write-Host "1. https://developer.xero.com/app/manage -> Create Web app" -ForegroundColor Yellow
    Write-Host "2. Redirect URI:" -ForegroundColor Yellow
    Write-Host "   https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/xero/callback" -ForegroundColor White
    Write-Host "3. Scopes: openid profile email accounting.transactions accounting.contacts offline_access" -ForegroundColor Yellow
    Write-Host "4. Run:" -ForegroundColor Yellow
    Write-Host '   $env:XERO_CLIENT_ID="<id>"; $env:XERO_CLIENT_SECRET="<secret>"; npm run xero:fill-env' -ForegroundColor White
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

Set-EnvLine "XERO_CLIENT_ID" $ClientId
Set-EnvLine "XERO_CLIENT_SECRET" $ClientSecret
$lines | Set-Content $OperatorFile -Encoding utf8

Write-Host "Updated $OperatorFile with Xero credentials" -ForegroundColor Green
if (-not $SkipRailway) {
    & (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")
}

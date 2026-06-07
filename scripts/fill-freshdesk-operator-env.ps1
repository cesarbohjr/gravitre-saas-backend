#Requires -Version 5.1
<#
.SYNOPSIS
  Merge Freshdesk OAuth credentials into backend/.env.operator.local and push to Railway.
#>
param(
    [string] $ClientId = $env:FRESHDESK_CLIENT_ID,
    [string] $ClientSecret = $env:FRESHDESK_CLIENT_SECRET,
    [switch] $SkipRailway
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not $ClientId -or -not $ClientSecret) {
    Write-Host "Freshdesk OAuth credentials required." -ForegroundColor Yellow
    Write-Host "1. Freshdesk Admin -> Apps -> Custom Apps -> OAuth" -ForegroundColor Yellow
    Write-Host "2. Redirect URI:" -ForegroundColor Yellow
    Write-Host "   https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/freshdesk/callback" -ForegroundColor White
    Write-Host "3. Customers enter their Freshdesk subdomain when connecting in Gravitre." -ForegroundColor Yellow
    Write-Host "4. Run:" -ForegroundColor Yellow
    Write-Host '   $env:FRESHDESK_CLIENT_ID="<id>"; $env:FRESHDESK_CLIENT_SECRET="<secret>"; npm run freshdesk:fill-env' -ForegroundColor White
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

Set-EnvLine "FRESHDESK_CLIENT_ID" $ClientId
Set-EnvLine "FRESHDESK_CLIENT_SECRET" $ClientSecret
$lines | Set-Content $OperatorFile -Encoding utf8

Write-Host "Updated $OperatorFile with Freshdesk credentials" -ForegroundColor Green
if (-not $SkipRailway) {
    & (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")
}

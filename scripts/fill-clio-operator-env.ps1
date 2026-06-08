#Requires -Version 5.1
<#
.SYNOPSIS
  Merge Clio OAuth credentials into backend/.env.operator.local and push to Railway.
#>
param(
    [string] $ClientId = $env:CLIO_CLIENT_ID,
    [string] $ClientSecret = $env:CLIO_CLIENT_SECRET,
    [switch] $SkipRailway
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not $ClientId -or -not $ClientSecret) {
    Write-Host "Clio OAuth credentials required." -ForegroundColor Yellow
    Write-Host "1. https://app.clio.com/settings/developer_applications" -ForegroundColor Yellow
    Write-Host "2. Redirect URI:" -ForegroundColor Yellow
    Write-Host "   https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/clio/callback" -ForegroundColor White
    Write-Host "3. Scopes: contacts_read matters_read" -ForegroundColor Yellow
    Write-Host "4. Run:" -ForegroundColor Yellow
    Write-Host '   $env:CLIO_CLIENT_ID="<id>"; $env:CLIO_CLIENT_SECRET="<secret>"; npm run clio:fill-env' -ForegroundColor White
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

Set-EnvLine "CLIO_CLIENT_ID" $ClientId
Set-EnvLine "CLIO_CLIENT_SECRET" $ClientSecret
$lines | Set-Content $OperatorFile -Encoding utf8

Write-Host "Updated $OperatorFile with Clio credentials" -ForegroundColor Green
if (-not $SkipRailway) {
    & (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")
}

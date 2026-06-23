#Requires -Version 5.1
<#
.SYNOPSIS
  Merge Zendesk OAuth credentials into backend/.env.operator.local and push to Railway.
#>
param(
    [string] $ClientId = $env:ZENDESK_CLIENT_ID,
    [string] $ClientSecret = $env:ZENDESK_CLIENT_SECRET,
    [switch] $SkipRailway
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not $ClientId -or -not $ClientSecret) {
    Write-Host "Zendesk OAuth credentials required." -ForegroundColor Yellow
    Write-Host "1. Zendesk Admin Center -> Apps and integrations -> Zendesk API -> OAuth Clients" -ForegroundColor Yellow
    Write-Host "2. Redirect URI:" -ForegroundColor Yellow
    Write-Host "   https://gravitre.app/api/connectors/oauth/zendesk/callback" -ForegroundColor White
    Write-Host "3. Scopes: read write" -ForegroundColor Yellow
    Write-Host "4. Run:" -ForegroundColor Yellow
    Write-Host '   $env:ZENDESK_CLIENT_ID="<client-id>"; $env:ZENDESK_CLIENT_SECRET="<secret>"; npm run zendesk:fill-env' -ForegroundColor White
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

Set-EnvLine "ZENDESK_CLIENT_ID" $ClientId
Set-EnvLine "ZENDESK_CLIENT_SECRET" $ClientSecret
$lines | Set-Content $OperatorFile -Encoding utf8

Write-Host "Updated $OperatorFile with Zendesk credentials" -ForegroundColor Green
if (-not $SkipRailway) {
    & (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")
}

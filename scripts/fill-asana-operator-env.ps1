#Requires -Version 5.1
<#
.SYNOPSIS
  Merge Asana OAuth credentials into backend/.env.operator.local and push to Railway.
#>
param(
    [string] $ClientId = $env:ASANA_CLIENT_ID,
    [string] $ClientSecret = $env:ASANA_CLIENT_SECRET,
    [switch] $SkipRailway
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not $ClientId -or -not $ClientSecret) {
    Write-Host "Asana OAuth credentials required." -ForegroundColor Yellow
    Write-Host "1. https://app.asana.com/0/my-apps -> Create app" -ForegroundColor Yellow
    Write-Host "2. Redirect URI:" -ForegroundColor Yellow
    Write-Host "   https://api.gravitre.app/api/connectors/oauth/asana/callback" -ForegroundColor White
    Write-Host "3. Scopes: default (or tasks/projects as needed in Asana app settings)" -ForegroundColor Yellow
    Write-Host "4. Run:" -ForegroundColor Yellow
    Write-Host '   $env:ASANA_CLIENT_ID="<id>"; $env:ASANA_CLIENT_SECRET="<secret>"; npm run asana:fill-env' -ForegroundColor White
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

Set-EnvLine "ASANA_CLIENT_ID" $ClientId
Set-EnvLine "ASANA_CLIENT_SECRET" $ClientSecret
$lines | Set-Content $OperatorFile -Encoding utf8

Write-Host "Updated $OperatorFile with Asana credentials" -ForegroundColor Green
if (-not $SkipRailway) {
    & (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")
}

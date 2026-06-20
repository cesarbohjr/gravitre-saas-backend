#Requires -Version 5.1
<#
.SYNOPSIS
  Merge Airtable OAuth credentials into backend/.env.operator.local and push to Railway.
#>
param(
    [string] $ClientId = $env:AIRTABLE_CLIENT_ID,
    [string] $ClientSecret = $env:AIRTABLE_CLIENT_SECRET,
    [switch] $SkipRailway
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not $ClientId -or -not $ClientSecret) {
    Write-Host "Airtable OAuth credentials required." -ForegroundColor Yellow
    Write-Host "1. https://airtable.com/create/oauth -> Register OAuth integration" -ForegroundColor Yellow
    Write-Host "2. Redirect URI:" -ForegroundColor Yellow
    Write-Host "   https://api.gravitre.app/api/connectors/oauth/airtable/callback" -ForegroundColor White
    Write-Host "3. Scopes: data.records:read data.records:write schema.bases:read" -ForegroundColor Yellow
    Write-Host "4. Run:" -ForegroundColor Yellow
    Write-Host '   $env:AIRTABLE_CLIENT_ID="<id>"; $env:AIRTABLE_CLIENT_SECRET="<secret>"; npm run airtable:fill-env' -ForegroundColor White
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

Set-EnvLine "AIRTABLE_CLIENT_ID" $ClientId
Set-EnvLine "AIRTABLE_CLIENT_SECRET" $ClientSecret
$lines | Set-Content $OperatorFile -Encoding utf8

Write-Host "Updated $OperatorFile with Airtable credentials" -ForegroundColor Green
if (-not $SkipRailway) {
    & (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")
}

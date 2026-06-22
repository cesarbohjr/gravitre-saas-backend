#Requires -Version 5.1
<#
.SYNOPSIS
  Merge Marketo OAuth credentials into backend/.env.operator.local and push to Railway.
#>
param(
    [string] $ClientId = $env:MARKETO_CLIENT_ID,
    [string] $ClientSecret = $env:MARKETO_CLIENT_SECRET,
    [switch] $SkipRailway
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not $ClientId -or -not $ClientSecret) {
    Write-Host "Marketo OAuth credentials required." -ForegroundColor Yellow
    Write-Host "1. Adobe Admin Console -> Marketo -> Launch -> API Integration" -ForegroundColor Yellow
    Write-Host "2. Redirect URI:" -ForegroundColor Yellow
    Write-Host "   https://api.gravitre.app/api/connectors/oauth/marketo/callback" -ForegroundColor White
    Write-Host "3. Customers enter Munchkin ID when connecting." -ForegroundColor Yellow
    Write-Host "4. Run:" -ForegroundColor Yellow
    Write-Host '   $env:MARKETO_CLIENT_ID="<id>"; $env:MARKETO_CLIENT_SECRET="<secret>"; npm run marketo:fill-env' -ForegroundColor White
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

Set-EnvLine "MARKETO_CLIENT_ID" $ClientId
Set-EnvLine "MARKETO_CLIENT_SECRET" $ClientSecret
$lines | Set-Content $OperatorFile -Encoding utf8

Write-Host "Updated $OperatorFile with Marketo credentials" -ForegroundColor Green
if (-not $SkipRailway) {
    & (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")
}

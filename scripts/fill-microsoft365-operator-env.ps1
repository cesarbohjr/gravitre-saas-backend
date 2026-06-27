#Requires -Version 5.1
<#
.SYNOPSIS
  Merge Microsoft 365 OAuth credentials into backend/.env.operator.local and push to Railway.
#>
param(
    [string] $ClientId = $env:MICROSOFT365_CLIENT_ID,
    [string] $ClientSecret = $env:MICROSOFT365_CLIENT_SECRET,
    [switch] $SkipRailway
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not $ClientId -or -not $ClientSecret) {
    Write-Host "Microsoft 365 OAuth credentials required." -ForegroundColor Yellow
    Write-Host "1. https://entra.microsoft.com -> App registrations -> New registration (multitenant Web)" -ForegroundColor Yellow
    Write-Host "2. Redirect URI:" -ForegroundColor Yellow
    Write-Host "   https://api.gravitre.app/api/connectors/oauth/microsoft365/callback" -ForegroundColor White
    Write-Host "3. Graph delegated scopes (add all):" -ForegroundColor Yellow
    Write-Host "   offline_access User.Read Mail.Read Mail.Send Calendars.ReadWrite Files.ReadWrite.All" -ForegroundColor White
    Write-Host "   ChannelMessage.Send Team.ReadBasic.All Channel.ReadBasic.All ChannelMessage.Read.All" -ForegroundColor White
    Write-Host "   OnlineMeetings.ReadWrite Sites.Read.All Sites.ReadWrite.All" -ForegroundColor White
    Write-Host "4. Use Client secret VALUE (not Secret ID) from Certificates & secrets" -ForegroundColor Yellow
    Write-Host "5. Run:" -ForegroundColor Yellow
    Write-Host '   $env:MICROSOFT365_CLIENT_ID="<app-id>"; $env:MICROSOFT365_CLIENT_SECRET="<secret-value>"; npm run microsoft365:fill-env' -ForegroundColor White
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

Set-EnvLine "MICROSOFT365_CLIENT_ID" $ClientId
Set-EnvLine "MICROSOFT365_CLIENT_SECRET" $ClientSecret
$lines | Set-Content $OperatorFile -Encoding utf8

Write-Host "Updated $OperatorFile with Microsoft 365 credentials" -ForegroundColor Green
if (-not $SkipRailway) {
    & (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")
}

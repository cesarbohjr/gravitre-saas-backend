#Requires -Version 5.1
<#
.SYNOPSIS
  Merge HubSpot OAuth credentials into backend/.env.operator.local and push to Railway.

.PARAMETER ClientId
  HubSpot app Client ID (Auth tab). Or set env HUBSPOT_CLIENT_ID.

.PARAMETER ClientSecret
  HubSpot app Client secret. Or set env HUBSPOT_CLIENT_SECRET.

.PARAMETER AppId
  Defaults to value from `hs project info` when omitted.

.PARAMETER SkipRailway
  Only update the local operator env file.
#>
param(
    [string] $ClientId = $env:HUBSPOT_CLIENT_ID,
    [string] $ClientSecret = $env:HUBSPOT_CLIENT_SECRET,
    [string] $AppId = $env:HUBSPOT_APP_ID,
    [switch] $SkipRailway
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"
$HubspotLocal = Join-Path $RepoRoot "backend\.env.hubspot.local"
$ProjectDir = Join-Path $RepoRoot "integrations\hubspot-app"

if (-not $ClientId -or -not $ClientSecret) {
    if (Test-Path $HubspotLocal) {
        $parsed = @{}
        Get-Content $HubspotLocal | ForEach-Object {
            $line = $_.Trim()
            if (-not $line -or $line.StartsWith("#")) { return }
            $idx = $line.IndexOf("=")
            if ($idx -lt 1) { return }
            $parsed[$line.Substring(0, $idx).Trim()] = $line.Substring($idx + 1).Trim().Trim('"')
        }
        if (-not $ClientId -and $parsed["HUBSPOT_CLIENT_ID"]) { $ClientId = $parsed["HUBSPOT_CLIENT_ID"] }
        if (-not $ClientSecret -and $parsed["HUBSPOT_CLIENT_SECRET"]) { $ClientSecret = $parsed["HUBSPOT_CLIENT_SECRET"] }
        if (-not $AppId -and $parsed["HUBSPOT_APP_ID"]) { $AppId = $parsed["HUBSPOT_APP_ID"] }
    }
}

if (-not $AppId -and (Get-Command hs -ErrorAction SilentlyContinue) -and (Test-Path $ProjectDir)) {
    Push-Location $ProjectDir
    try {
        $info = hs project info 2>&1 | Out-String
        if ($info -match "App ID:\s*(\d+)") { $AppId = $Matches[1] }
    } catch {
        Write-Host "Could not read App ID from hs project info (optional)." -ForegroundColor Yellow
    } finally {
        Pop-Location
    }
}
if (-not $AppId) { $AppId = "41541133" }

if (-not $ClientId -or -not $ClientSecret) {
    Write-Host "HubSpot Client ID and secret are required." -ForegroundColor Yellow
    Write-Host "1. Run: cd integrations/hubspot-app; hs project open" -ForegroundColor Yellow
    Write-Host "2. Open Gravitre Operator -> Auth -> copy Client ID and Client secret" -ForegroundColor Yellow
    Write-Host "3. Re-run:" -ForegroundColor Yellow
    Write-Host '   $env:HUBSPOT_CLIENT_ID="<id>"; $env:HUBSPOT_CLIENT_SECRET="<secret>"; .\scripts\fill-hubspot-operator-env.ps1' -ForegroundColor Yellow
    Write-Host "Or copy backend/.env.hubspot.local.example to backend/.env.hubspot.local and fill values." -ForegroundColor Yellow
    exit 1
}

$lines = @()
if (Test-Path $OperatorFile) {
    $lines = Get-Content $OperatorFile
}

function Set-EnvLine([string]$Key, [string]$Value) {
    $script:lines = $script:lines | Where-Object {
        $t = $_.Trim()
        -not ($t -and -not $t.StartsWith("#") -and $t.StartsWith("$Key="))
    }
    $script:lines += "$Key=$Value"
}

Set-EnvLine "HUBSPOT_CLIENT_ID" $ClientId
Set-EnvLine "HUBSPOT_CLIENT_SECRET" $ClientSecret
if ($AppId) { Set-EnvLine "HUBSPOT_APP_ID" $AppId }

if (-not ($lines | Where-Object { $_ -match "^API_PUBLIC_URL=" })) {
    $lines += "API_PUBLIC_URL=https://api.gravitre.app"
}
if (-not ($lines | Where-Object { $_ -match "^PUBLIC_APP_URL=" })) {
    $lines += "PUBLIC_APP_URL=https://gravitre.app"
}

$lines | Set-Content $OperatorFile -Encoding utf8
Write-Host "Updated $OperatorFile" -ForegroundColor Green

if ($SkipRailway) { exit 0 }
& (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")

#Requires -Version 5.1
<#
.SYNOPSIS
  Merge Gravitre OAuth credentials into backend/.env.operator.local and push to Railway.

  Accepts GOOGLE_OAUTH_* or GOOGLE_ANALYTICS_* (same values written to both for compatibility).
#>
param(
    [string] $ClientId = $(if ($env:GOOGLE_OAUTH_CLIENT_ID) { $env:GOOGLE_OAUTH_CLIENT_ID } else { $env:GOOGLE_ANALYTICS_CLIENT_ID }),
    [string] $ClientSecret = $(if ($env:GOOGLE_OAUTH_CLIENT_SECRET) { $env:GOOGLE_OAUTH_CLIENT_SECRET } else { $env:GOOGLE_ANALYTICS_CLIENT_SECRET }),
    [string] $ClientSecretsJsonPath,
    [switch] $SkipRailway
)

if ($ClientSecretsJsonPath -and (Test-Path $ClientSecretsJsonPath)) {
    $raw = Get-Content $ClientSecretsJsonPath -Raw | ConvertFrom-Json
    $web = $raw.web
    if (-not $web) { $web = $raw.installed }
    if ($web) {
        if (-not $ClientId) { $ClientId = $web.client_id }
        if (-not $ClientSecret) { $ClientSecret = $web.client_secret }
    }
}

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not $ClientId -or -not $ClientSecret) {
    Write-Host "Set GOOGLE_OAUTH_CLIENT_ID/SECRET or GOOGLE_ANALYTICS_CLIENT_ID/SECRET, or pass -ClientId/-ClientSecret" -ForegroundColor Red
    exit 1
}

$lines = @()
if (Test-Path $OperatorFile) {
    $lines = Get-Content $OperatorFile
}

function Set-EnvLine {
    param([string[]] $Content, [string] $Key, [string] $Value)
    $found = $false
    $out = @()
    foreach ($line in $Content) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=") {
            $out += "${Key}=$Value"
            $found = $true
        } else {
            $out += $line
        }
    }
    if (-not $found) {
        $out += "${Key}=$Value"
    }
    return $out
}

foreach ($key in @(
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_ANALYTICS_CLIENT_ID",
    "GOOGLE_ANALYTICS_CLIENT_SECRET"
)) {
    $val = if ($key -like "*SECRET*") { $ClientSecret } else { $ClientId }
    $lines = Set-EnvLine $lines $key $val
}

if (-not ($lines -join "`n" -match "API_PUBLIC_URL=")) {
    $lines += "API_PUBLIC_URL=https://api.gravitre.app"
}
if (-not ($lines -join "`n" -match "PUBLIC_APP_URL=")) {
    $lines += "PUBLIC_APP_URL=https://gravitre.app"
}

Set-Content -Path $OperatorFile -Value ($lines -join "`r`n") -Encoding utf8
Write-Host "Updated $OperatorFile (GOOGLE_OAUTH_* + GOOGLE_ANALYTICS_*)" -ForegroundColor Green

if (-not $SkipRailway) {
    & (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")
}

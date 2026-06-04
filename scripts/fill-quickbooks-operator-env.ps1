#Requires -Version 5.1
<#
.SYNOPSIS
  Merge QuickBooks OAuth credentials into backend/.env.operator.local and push to Railway.

.PARAMETER ClientId
  Intuit app Client ID. Or set env QUICKBOOKS_CLIENT_ID.

.PARAMETER ClientSecret
  Intuit app Client secret. Or set env QUICKBOOKS_CLIENT_SECRET.

.PARAMETER SkipRailway
  Only update the local operator env file.
#>
param(
    [string] $ClientId = $env:QUICKBOOKS_CLIENT_ID,
    [string] $ClientSecret = $env:QUICKBOOKS_CLIENT_SECRET,
    [switch] $SkipRailway
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not $ClientId -or -not $ClientSecret) {
    Write-Host "Provide -ClientId/-ClientSecret or set QUICKBOOKS_CLIENT_ID and QUICKBOOKS_CLIENT_SECRET" -ForegroundColor Red
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

$lines = Set-EnvLine $lines "QUICKBOOKS_CLIENT_ID" $ClientId
$lines = Set-EnvLine $lines "QUICKBOOKS_CLIENT_SECRET" $ClientSecret
if (-not ($lines -join "`n" -match "API_PUBLIC_URL=")) {
    $lines += "API_PUBLIC_URL=https://gravitre-saas-backend-production.up.railway.app"
}
Set-Content -Path $OperatorFile -Value ($lines -join "`r`n") -Encoding utf8
Write-Host "Updated $OperatorFile" -ForegroundColor Green

if (-not $SkipRailway) {
    & (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")
}

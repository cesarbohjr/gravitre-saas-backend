#Requires -Version 5.1
<#
.SYNOPSIS
  Merge Voyage AI credentials into backend/.env.operator.local and push to Railway.

.PARAMETER ApiKey
  Voyage API key from https://dash.voyageai.com/ . Or set env VOYAGE_API_KEY.

.PARAMETER SkipRailway
  Only update the local operator env file.
#>
param(
    [string] $ApiKey = $env:VOYAGE_API_KEY,
    [switch] $SkipRailway
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not $ApiKey) {
    Write-Host "VOYAGE_API_KEY is required." -ForegroundColor Yellow
    Write-Host "1. Create a key at https://dash.voyageai.com/" -ForegroundColor Yellow
    Write-Host "2. Re-run:" -ForegroundColor Yellow
    Write-Host '   $env:VOYAGE_API_KEY="<key>"; .\scripts\fill-voyage-operator-env.ps1' -ForegroundColor Yellow
    Write-Host "Or: npm run ai:fill-voyage-env (after setting VOYAGE_API_KEY in your shell)" -ForegroundColor Yellow
    exit 1
}

& (Join-Path $RepoRoot "scripts\init-operator-platform.ps1") | Out-Null

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

Set-EnvLine "VOYAGE_API_KEY" $ApiKey.Trim()
Set-EnvLine "VOYAGE_EMBEDDING_ENABLED" "false"

$lines | Set-Content $OperatorFile -Encoding utf8
Write-Host "Updated $OperatorFile (VOYAGE_API_KEY, VOYAGE_EMBEDDING_ENABLED=false)" -ForegroundColor Green

if ($SkipRailway) {
    Write-Host "Skipped Railway push. To sync prod later: npm run ai:push-railway-env" -ForegroundColor Yellow
    exit 0
}

& (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")

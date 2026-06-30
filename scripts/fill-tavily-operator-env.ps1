#Requires -Version 5.1
<#
.SYNOPSIS
  Merge Tavily web-search credentials into backend/.env.operator.local and push to Railway.
#>
param(
    [string] $ApiKey = $env:TAVILY_API_KEY,
    [switch] $SkipRailway
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not $ApiKey) {
    Write-Host "Tavily API key required for assistant web search." -ForegroundColor Yellow
    Write-Host "1. Create a key at https://tavily.com" -ForegroundColor Yellow
    Write-Host "2. Run:" -ForegroundColor Yellow
    Write-Host '   $env:TAVILY_API_KEY="tvly-..."; npm run tavily:fill-env' -ForegroundColor White
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

Set-EnvLine "TAVILY_API_KEY" $ApiKey
$lines | Set-Content $OperatorFile -Encoding utf8

Write-Host "Updated $OperatorFile with TAVILY_API_KEY" -ForegroundColor Green
if (-not $SkipRailway) {
    & (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")
}

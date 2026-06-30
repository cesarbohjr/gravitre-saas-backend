#Requires -Version 5.1
<#
.SYNOPSIS
  Create Marketing Operations Pack Phase 5-8 audit tickets in Linear.

.DESCRIPTION
  Resolves LINEAR_API_KEY from (in order):
    1. LINEAR_API_KEY / LINEAR_TOKEN env var
    2. backend/.env.operator.local
    3. Railway service variables (requires railway login + link)

  Never prints the key value.
#>
param(
    [string] $Service = "gravitre-saas-backend"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

function Read-EnvFileKey([string]$Path, [string]$Key) {
    if (-not (Test-Path $Path)) { return $null }
    foreach ($line in Get-Content $Path) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith("#")) { continue }
        if ($t.StartsWith("$Key=")) {
            return $t.Substring($Key.Length + 1).Trim()
        }
    }
    return $null
}

$key = [string]$env:LINEAR_API_KEY
if (-not $key.Trim()) { $key = [string]$env:LINEAR_TOKEN }
if (-not $key.Trim()) { $key = [string](Read-EnvFileKey $OperatorFile "LINEAR_API_KEY") }
if (-not $key.Trim()) { $key = [string](Read-EnvFileKey $OperatorFile "LINEAR_TOKEN") }

if (-not $key.Trim()) {
    if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
        Write-Host "No LINEAR_API_KEY found locally and Railway CLI is not installed." -ForegroundColor Red
        Write-Host "Either: railway login && npm run linear:marketing-pack-audit" -ForegroundColor Yellow
        Write-Host "Or set LINEAR_API_KEY in backend/.env.operator.local" -ForegroundColor Yellow
        exit 1
    }
    $rawJson = railway variables --service $Service --json 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Could not read Railway variables. Run: railway login; railway link" -ForegroundColor Red
        Write-Host $rawJson -ForegroundColor Yellow
        exit $LASTEXITCODE
    }
    $remote = $rawJson | ConvertFrom-Json
    $key = [string]$remote.LINEAR_API_KEY
    if (-not $key.Trim()) { $key = [string]$remote.LINEAR_TOKEN }
    if (-not $key.Trim()) {
        Write-Host "LINEAR_API_KEY not found on Railway service '$Service'." -ForegroundColor Red
        exit 1
    }
    Write-Host "Using LINEAR_API_KEY from Railway ($Service); value not printed." -ForegroundColor Green
} else {
    Write-Host "Using LINEAR_API_KEY from local env; value not printed." -ForegroundColor Green
}

$env:LINEAR_API_KEY = $key.Trim()

Push-Location $RepoRoot
try {
    $scriptPath = Join-Path $RepoRoot "scripts\create-marketing-pack-audit-linear-issues.mjs"
    node $scriptPath
    exit $LASTEXITCODE
} finally {
    Pop-Location
}

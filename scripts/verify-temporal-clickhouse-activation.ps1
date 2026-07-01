#Requires -Version 5.1
<#
.SYNOPSIS
  Verify Temporal + ClickHouse activation on Railway production.

.DESCRIPTION
  Requires `railway login` and INTERNAL_API_SECRET in backend/.env.operator.local.
  Calls the deployed infrastructure-health endpoint (runs inside Railway env).
#>
param(
    [string] $Service = "gravitre-saas-backend",
    [string] $ApiBase = "https://api.gravitre.app",
    [string] $OperatorFile = $(Join-Path (Split-Path -Parent $PSScriptRoot) "backend\.env.operator.local")
)

$ErrorActionPreference = "Stop"

function Get-EnvValue([string]$File, [string]$Key) {
    if (-not (Test-Path $File)) { return $null }
    foreach ($line in Get-Content $File) {
        $t = $line.Trim()
        if ($t -and -not $t.StartsWith("#") -and $t.StartsWith("$Key=")) {
            return $t.Substring($Key.Length + 1).Trim()
        }
    }
    return $null
}

# Load RAILWAY_TOKEN from operator file if not already set
if (-not $env:RAILWAY_TOKEN -and (Test-Path $OperatorFile)) {
    $tokenLine = Get-Content $OperatorFile | Where-Object { $_ -match '^\s*RAILWAY_TOKEN=' } | Select-Object -First 1
    if ($tokenLine) {
        $env:RAILWAY_TOKEN = ($tokenLine -replace '^\s*RAILWAY_TOKEN=','').Trim()
    }
}

Write-Host "=== A1: Railway variable presence ===" -ForegroundColor Cyan
if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Host "Railway CLI not installed." -ForegroundColor Red
    exit 1
}
$rawJson = railway variables --service $Service --json 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "railway variables failed - run: railway login" -ForegroundColor Red
    exit $LASTEXITCODE
}
$remote = $rawJson | ConvertFrom-Json
$required = @(
    "TEMPORAL_HOST", "TEMPORAL_NAMESPACE", "TEMPORAL_API_KEY",
    "CLICKHOUSE_HOST", "CLICKHOUSE_PORT", "CLICKHOUSE_USER",
    "CLICKHOUSE_PASSWORD", "CLICKHOUSE_DATABASE"
)
$missing = @()
foreach ($key in $required) {
    $present = [bool]([string]$remote.$key).Trim()
    Write-Host ("  {0}: {1}" -f $key, $(if ($present) { "set" } else { "MISSING" }))
    if (-not $present) { $missing += $key }
}
if ($missing.Count -gt 0) {
    Write-Host "Missing required Railway variables: $($missing -join ', ')" -ForegroundColor Red
    exit 1
}

$secret = Get-EnvValue $OperatorFile "INTERNAL_API_SECRET"
if (-not $secret) {
    Write-Host "INTERNAL_API_SECRET not found in $OperatorFile" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== A4-A5: Apply schema + health check (production process) ===" -ForegroundColor Cyan
$uri = "$ApiBase/api/internal/ops/infrastructure-health?apply_clickhouse_schema=true"
$response = Invoke-RestMethod -Uri $uri -Headers @{ "X-Internal-Secret" = $secret } -Method Get
$response | ConvertTo-Json -Depth 8

if (-not $response.ok) {
    Write-Host "Infrastructure health check failed." -ForegroundColor Red
    exit 1
}

Write-Host "`n=== A7: Trigger Temporal company-intelligence workflow ===" -ForegroundColor Cyan
$triggerUri = "$ApiBase/api/internal/ops/company-intelligence-run"
$trigger = Invoke-RestMethod -Uri $triggerUri -Headers @{ "X-Internal-Secret" = $secret; "Content-Type" = "application/json" } -Method Post -Body "{}"
$trigger | ConvertTo-Json -Depth 6

Write-Host "`nAll activation checks passed. Confirm workflow in Temporal Cloud UI." -ForegroundColor Green

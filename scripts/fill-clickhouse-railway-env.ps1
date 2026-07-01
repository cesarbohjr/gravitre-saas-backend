#Requires -Version 5.1
<#
.SYNOPSIS
  Set ClickHouse SQL password on Railway (from env or prompt).

.DESCRIPTION
  Reset the password in ClickHouse Cloud first, then run:
    $env:CLICKHOUSE_PASSWORD = '<password from clickhouse.cloud>'
    npm run clickhouse:push-railway-env
#>
param(
    [string] $Service = "gravitre-saas-backend",
    [string] $OperatorFile = $(Join-Path (Split-Path -Parent $PSScriptRoot) "backend\.env.operator.local")
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Host "Railway CLI not installed." -ForegroundColor Red
    exit 1
}

if (-not $env:RAILWAY_TOKEN -and (Test-Path $OperatorFile)) {
    $tokenLine = Get-Content $OperatorFile | Where-Object { $_ -match '^\s*RAILWAY_TOKEN=' } | Select-Object -First 1
    if ($tokenLine) {
        $env:RAILWAY_TOKEN = ($tokenLine -replace '^\s*RAILWAY_TOKEN=','').Trim()
    }
}

$password = $env:CLICKHOUSE_PASSWORD
if (-not $password) {
    $secure = Read-Host "ClickHouse SQL password (from clickhouse.cloud)" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

if (-not $password) {
    Write-Host "CLICKHOUSE_PASSWORD is required." -ForegroundColor Red
    exit 1
}

railway variables --service $Service --set "CLICKHOUSE_PASSWORD=$password" | Out-Null
Write-Host "Updated CLICKHOUSE_PASSWORD on Railway service $Service" -ForegroundColor Green
Write-Host "Redeploy or wait for auto-deploy, then run: npm run infra:verify" -ForegroundColor Yellow

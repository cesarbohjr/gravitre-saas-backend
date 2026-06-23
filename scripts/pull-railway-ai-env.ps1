#Requires -Version 5.1
<#
.SYNOPSIS
  Pull AI/RAG secrets from Railway into backend/.env.operator.local (never prints values).

.DESCRIPTION
  Merges VOYAGE_API_KEY, OPENAI_API_KEY, and VOYAGE_EMBEDDING_ENABLED from the
  gravitre-saas-backend Railway service into the gitignored operator env file.
#>
param(
    [string] $Service = "gravitre-saas-backend",
    [string] $OperatorFile = $(Join-Path (Split-Path -Parent $PSScriptRoot) "backend\.env.operator.local")
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Host "Railway CLI not found. Install: npm i -g @railway/cli" -ForegroundColor Red
    exit 1
}

& (Join-Path $RepoRoot "scripts\init-operator-platform.ps1") | Out-Null

$rawJson = railway variables --service $Service --json 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "railway variables failed (exit $LASTEXITCODE). Link project: railway link" -ForegroundColor Red
    exit $LASTEXITCODE
}

$remote = $rawJson | ConvertFrom-Json
if (-not $remote) {
    Write-Host "Could not parse Railway variables JSON." -ForegroundColor Red
    exit 1
}

$lines = Get-Content $OperatorFile
function Set-EnvLine([string]$Key, [string]$Value) {
    $script:lines = $script:lines | Where-Object {
        $t = $_.Trim()
        -not ($t -and -not $t.StartsWith("#") -and $t.StartsWith("$Key="))
    }
    $script:lines += "$Key=$Value"
}

$pullKeys = @(
    "VOYAGE_API_KEY",
    "OPENAI_API_KEY",
    "VOYAGE_EMBEDDING_ENABLED"
)

$updated = @()
$missing = @()
foreach ($key in $pullKeys) {
    $value = [string]$remote.$key
    if ($value -and $value.Trim()) {
        Set-EnvLine $key $value.Trim()
        $updated += $key
    } else {
        $missing += $key
    }
}

$lines | Set-Content $OperatorFile -Encoding utf8

Write-Host "Updated $OperatorFile" -ForegroundColor Green
if ($updated.Count -gt 0) {
    Write-Host ("  set: " + ($updated -join ", ")) -ForegroundColor Green
}
if ($missing.Count -gt 0) {
    Write-Host ("  missing on Railway: " + ($missing -join ", ")) -ForegroundColor Yellow
    if ($missing -contains "VOYAGE_API_KEY") {
        Write-Host "  Voyage is not configured on Railway yet. Set a key locally:" -ForegroundColor Yellow
        Write-Host '    $env:VOYAGE_API_KEY="<key>"; npm run ai:fill-voyage-env' -ForegroundColor Yellow
    }
    Write-Host "  After Railway has the vars, re-run: npm run ai:pull-railway-env" -ForegroundColor Yellow
}

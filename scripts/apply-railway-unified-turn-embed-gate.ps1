#Requires -Version 5.1
<#
.SYNOPSIS
  Toggle unified-turn embedding retrieval gate on Railway for live A/B.

.EXAMPLE
  .\scripts\apply-railway-unified-turn-embed-gate.ps1 -Mode keyword-at-57
  .\scripts\apply-railway-unified-turn-embed-gate.ps1 -Mode embedding-at-57
#>
param(
    [ValidateSet("keyword-at-57", "embedding-at-57", "embed-at-70")]
    [string] $Mode,
    [string] $Service = "gravitre-saas-backend",
    [string] $EnvFile = $(Join-Path (Split-Path -Parent $PSScriptRoot) "backend\.env.operator.local")
)

$ErrorActionPreference = "Stop"

if (-not $env:RAILWAY_TOKEN -and (Test-Path $EnvFile)) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim().Trim('"')
        if ($key -eq "RAILWAY_TOKEN" -and $val) { $env:RAILWAY_TOKEN = $val }
    }
}

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Error "Install Railway CLI: npm i -g @railway/cli"
}
if (-not $env:RAILWAY_TOKEN) {
    Write-Error "RAILWAY_TOKEN not set (backend/.env.operator.local or env)."
}

switch ($Mode) {
    "keyword-at-57" {
        # Force keyword narrow at current catalog size (57 tools): raise gate above catalog.
        railway variables set "UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS=999" --service $Service | Out-Null
        Write-Host "Set UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS=999 (keyword path at 57 tools). Redeploy backend and wait for /health git_sha."
    }
    "embedding-at-57" {
        railway variables set "UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS=200" --service $Service | Out-Null
        Write-Host "Set UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS=200 (code default; embedding off until catalog >= 200)."
    }
    "embed-at-70" {
        railway variables set "UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS=40" --service $Service | Out-Null
        Write-Host "Set UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS=40 (embedding path at ~70 tools for A/B). Redeploy backend and wait for /health git_sha."
    }
}

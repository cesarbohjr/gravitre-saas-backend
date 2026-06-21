#Requires -Version 5.1
<#
.SYNOPSIS
  STA-270 paired evaluation: baseline (flag off) then coordination (flag on).

.DESCRIPTION
  1. Captures baseline smoke with --expect-disabled
  2. Prompts to enable Railway flag (npm run coordination:railway-on)
  3. Captures flag-on smoke with --expect-enabled

  Decision gate: STA-258 due 2026-08-01
#>
param(
    [switch] $SkipRailwayPrompt
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot

Write-Host "=== STA-270 baseline (flag off) ===" -ForegroundColor Cyan
python scripts/smoke-sta270-coordination-layer.py `
    --expect-disabled `
    --json docs/delivery/smoke-sta270-baseline-off-latest.json
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }

if (-not $SkipRailwayPrompt) {
    Write-Host ""
    Write-Host "Enable CoordinationLayer on Railway (test org only), then press Enter." -ForegroundColor Yellow
    Write-Host "  railway login" -ForegroundColor DarkGray
    Write-Host "  npm run coordination:railway-on" -ForegroundColor DarkGray
    Read-Host "Press Enter after Railway redeploy completes"
}

Write-Host "=== STA-270 coordination path (flag on) ===" -ForegroundColor Cyan
python scripts/smoke-sta270-coordination-layer.py `
    --expect-enabled `
    --json docs/delivery/smoke-sta270-coordination-on-latest.json
$code = $LASTEXITCODE
Pop-Location
exit $code

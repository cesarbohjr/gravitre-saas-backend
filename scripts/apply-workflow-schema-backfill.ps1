# STA-271 C.4: backfill legacy workflow tables into contract tables (idempotent).
# Requires: supabase login + link to prod project (smyeexlrqdpymwjmgzqu)
#
# Usage:
#   .\scripts\apply-workflow-schema-backfill.ps1
#   .\scripts\apply-workflow-schema-backfill.ps1 -VerifyOnly

param(
    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backfill = Join-Path $repoRoot "supabase\scripts\legacy\backfill_workflow_contract_tables.sql"
$verify = Join-Path $repoRoot "supabase\scripts\legacy\verify_backfill.sql"

Push-Location $repoRoot
try {
    if (-not $VerifyOnly) {
        if (-not (Test-Path $backfill)) {
            Write-Error "Backfill SQL not found: $backfill"
        }
        Write-Host "Applying workflow schema backfill to linked Supabase project..."
        supabase db query --linked -f $backfill
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Backfill SQL failed (exit $LASTEXITCODE)"
        }
    }

    Write-Host "Running verify_backfill.sql..."
    supabase db query --linked -f $verify
    if ($LASTEXITCODE -ne 0) {
        Write-Error "verify_backfill.sql failed (exit $LASTEXITCODE)"
    }

    Write-Host "Workflow schema backfill verification complete."
}
finally {
    Pop-Location
}

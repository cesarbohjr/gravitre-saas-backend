# STA-263 remediation: apply execution_verified migration, then force-fail stuck smoke swarms.
# Requires: supabase login + link to supabase-green-flower (smyeexlrqdpymwjmgzqu)
#
# Usage:
#   .\scripts\remediate-smoke-swarm-runs.ps1
#   .\scripts\remediate-smoke-swarm-runs.ps1 -SkipMigration

param(
    [switch]$SkipMigration
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$migration = Join-Path $repoRoot "supabase\migrations\20260707120000_agent_swarm_execution_verified.sql"
$remediation = Join-Path $repoRoot "supabase\scripts\remediate_smoke_swarm_runs.sql"

Push-Location $repoRoot
try {
    if (-not $SkipMigration) {
        if (-not (Test-Path $migration)) {
            Write-Error "Migration not found: $migration"
        }
        Write-Host "Applying execution_verified migration to linked Supabase project..."
        supabase db push --include-all
        if ($LASTEXITCODE -ne 0) {
            Write-Error "supabase db push failed (exit $LASTEXITCODE)"
        }
    }

    Write-Host "Force-failing stuck Tier5 smoke swarm runs..."
    supabase db query --linked -f $remediation
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Remediation SQL failed (exit $LASTEXITCODE)"
    }

    Write-Host "Verifying smoke swarm rows..."
    supabase db query --linked -o json "SELECT id, status, execution_verified, left(error_message, 80) AS error_snippet, objective FROM public.agent_swarm_runs WHERE org_id = '00000000-0000-0000-0000-000000000001' AND objective ILIKE '%Tier5 smoke swarm%' ORDER BY created_at;"
}
finally {
    Pop-Location
}

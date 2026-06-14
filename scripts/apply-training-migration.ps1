# Applies training hub tables to the linked Supabase project (idempotent).
# Usage:
#   supabase login
#   supabase link --project-ref <your-project-ref>
#   .\scripts\apply-training-migration.ps1

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$migration = Join-Path $repoRoot "supabase\migrations\20260428174000_training_entities.sql"

if (-not (Test-Path $migration)) {
    Write-Error "Migration file not found: $migration"
}

Write-Host "Applying training hub migration via Supabase CLI..."
Write-Host "  $migration"

Push-Location $repoRoot
try {
    supabase db push --include-all
    if ($LASTEXITCODE -ne 0) {
        Write-Error "supabase db push failed (exit $LASTEXITCODE). Run the SQL manually in Supabase Dashboard > SQL Editor:"
        Write-Host (Get-Content $migration -Raw)
        exit $LASTEXITCODE
    }
    Write-Host "Training migration applied successfully."
}
finally {
    Pop-Location
}

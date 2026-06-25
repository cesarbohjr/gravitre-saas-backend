#Requires -Version 5.1
<#
.SYNOPSIS
  Apply Supabase migration that expands connectors.type allowed values.
#>
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not (Get-Command supabase -ErrorAction SilentlyContinue)) {
    Write-Host "Install Supabase CLI: https://supabase.com/docs/guides/cli" -ForegroundColor Red
    Write-Host "Or paste SQL from supabase/migrations/20260625120000_expand_connector_types_full_catalog.sql into the Supabase SQL editor." -ForegroundColor Yellow
    exit 1
}

Write-Host "Applying pending Supabase migrations (includes connector type expansion)..." -ForegroundColor Cyan
supabase db push
if ($LASTEXITCODE -ne 0) {
    Write-Host "supabase db push failed. Run the SQL file manually in Supabase Dashboard -> SQL." -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "Connector type constraint updated. Retry OAuth connect on /connectors." -ForegroundColor Green

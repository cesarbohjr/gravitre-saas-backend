#Requires -Version 5.1
<#
.SYNOPSIS
  Sync SUPABASE_SERVICE_ROLE_KEY from backend/.env to Vercel production + preview.
#>
param(
    [string] $EnvFile,
    [switch] $SkipPreview
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $EnvFile) {
    $EnvFile = Join-Path $RepoRoot "backend\.env"
}

function Read-DotEnvValue([string] $Path, [string] $Key) {
    if (-not (Test-Path $Path)) { return $null }
    foreach ($line in Get-Content $Path) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=\s*(.+)$") {
            return $matches[1].Trim().Trim('"')
        }
    }
    return $null
}

$serviceKey = Read-DotEnvValue $EnvFile "SUPABASE_SERVICE_ROLE_KEY"
if (-not $serviceKey) {
    Write-Host "SUPABASE_SERVICE_ROLE_KEY missing in $EnvFile" -ForegroundColor Red
    exit 1
}

if ($serviceKey.StartsWith("sb_publishable_")) {
    Write-Host "ERROR: Value looks like anon/publishable key, not service_role." -ForegroundColor Red
    exit 1
}

Push-Location $RepoRoot
try {
    if (-not (Test-Path (Join-Path $RepoRoot ".vercel\project.json"))) {
        vercel link --yes --project gravitre-saas-backend 2>&1 | Out-Host
    }

    $serviceKey | vercel env add SUPABASE_SERVICE_ROLE_KEY production --force 2>&1 | Out-Host
    Write-Host "Updated Vercel SUPABASE_SERVICE_ROLE_KEY (production)." -ForegroundColor Green

    if (-not $SkipPreview) {
        $serviceKey | vercel env add SUPABASE_SERVICE_ROLE_KEY preview --force 2>&1 | Out-Host
        Write-Host "Updated Vercel SUPABASE_SERVICE_ROLE_KEY (preview)." -ForegroundColor Green
    }
} finally {
    Pop-Location
}

#Requires -Version 5.1
<#
.SYNOPSIS
  Sync Supabase JWT secret to Vercel production (must match Railway SUPABASE_JWT_SECRET).

  Get the JWT Secret from:
  https://supabase.com/dashboard/project/smyeexlrqdpymwjmgzqu/settings/api
  (JWT Settings — NOT the service_role / sb_secret key)

  Store in backend/.env.operator.local as SUPABASE_JWT_SECRET=...
#>
param(
    [string] $JwtSecret,
    [string] $OperatorFile
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $OperatorFile) {
    $OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"
}

if (-not $JwtSecret -and (Test-Path $OperatorFile)) {
    Get-Content $OperatorFile | ForEach-Object {
        if ($_ -match '^\s*SUPABASE_JWT_SECRET\s*=\s*(.+)$') {
            $JwtSecret = $matches[1].Trim().Trim('"')
        }
    }
}

if (-not $JwtSecret) {
    Write-Host "SUPABASE_JWT_SECRET required." -ForegroundColor Red
    Write-Host "Add to backend/.env.operator.local or pass -JwtSecret" -ForegroundColor Yellow
    Write-Host "Dashboard: Project Settings -> API -> JWT Secret (not sb_secret_*)" -ForegroundColor Yellow
    exit 1
}

if ($JwtSecret.StartsWith("sb_secret_")) {
    Write-Host "WARNING: This looks like a Supabase API secret key, not the JWT signing secret." -ForegroundColor Yellow
    Write-Host "Use the JWT Secret from JWT Settings in the dashboard." -ForegroundColor Yellow
}

Push-Location (Join-Path $RepoRoot "apps\web")
try {
    $JwtSecret | vercel env add SUPABASE_JWT_SECRET production --force 2>&1 | Out-Host
    Write-Host "Updated Vercel SUPABASE_JWT_SECRET (production)." -ForegroundColor Green
    Write-Host "Ensure Railway gravitre-saas-backend uses the same value." -ForegroundColor Cyan
} finally {
    Pop-Location
}

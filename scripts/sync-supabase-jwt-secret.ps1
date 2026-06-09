#Requires -Version 5.1
<#
.SYNOPSIS
  Sync Supabase Legacy JWT Secret to Vercel + Railway + local backend/.env.

  Use Dashboard -> Settings -> JWT Keys -> Legacy JWT Secret (NOT sb_secret_* API keys).
  ES256 user tokens are verified via JWKS automatically; this secret is still used for
  legacy HS256 paths and should not be an API secret key.

  Store in backend/.env.operator.local as SUPABASE_JWT_SECRET=...
#>
param(
    [string] $JwtSecret,
    [string] $OperatorFile,
    [string] $RailwayService = "gravitre-saas-backend",
    [switch] $SkipVercel,
    [switch] $SkipRailway,
    [switch] $SkipLocalEnv
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $OperatorFile) {
    $OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"
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

function Set-DotEnvValue([string] $Path, [string] $Key, [string] $Value) {
    if (-not (Test-Path $Path)) {
        Set-Content -Path $Path -Value "$Key=$Value" -Encoding utf8
        return
    }
    $lines = Get-Content $Path
    $found = $false
    $updated = foreach ($line in $lines) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=") {
            $found = $true
            "$Key=$Value"
        } else {
            $line
        }
    }
    if (-not $found) {
        $updated += "$Key=$Value"
    }
    Set-Content -Path $Path -Value $updated -Encoding utf8
}

function Resolve-JwtSecret {
    param([string] $Explicit)
    if ($Explicit) { return $Explicit }
    $candidates = @(
        (Read-DotEnvValue $OperatorFile "SUPABASE_JWT_SECRET"),
        (Read-DotEnvValue (Join-Path $RepoRoot ".env.vercel.production") "SUPABASE_JWT_SECRET"),
        (Read-DotEnvValue (Join-Path $RepoRoot "backend\.env") "SUPABASE_JWT_SECRET")
    )
    foreach ($candidate in $candidates) {
        if (-not $candidate) { continue }
        if ($candidate.StartsWith("sb_secret_") -or $candidate.StartsWith("sb_publishable_")) { continue }
        return $candidate
    }
    return $null
}

$JwtSecret = Resolve-JwtSecret $JwtSecret

if (-not $JwtSecret) {
    Write-Host "SUPABASE_JWT_SECRET required." -ForegroundColor Red
    Write-Host "Add to backend/.env.operator.local or pass -JwtSecret" -ForegroundColor Yellow
    Write-Host "Dashboard: Settings -> JWT Keys -> Legacy JWT Secret" -ForegroundColor Yellow
    exit 1
}

if ($JwtSecret.StartsWith("sb_secret_") -or $JwtSecret.StartsWith("sb_publishable_")) {
    Write-Host "ERROR: Value looks like a Supabase API key, not the Legacy JWT Secret." -ForegroundColor Red
    Write-Host "Use JWT Keys -> Legacy JWT Secret (long base64 string ending with ==)." -ForegroundColor Yellow
    exit 1
}

if (-not $SkipLocalEnv) {
    Set-DotEnvValue (Join-Path $RepoRoot "backend\.env") "SUPABASE_JWT_SECRET" $JwtSecret
    Write-Host "Updated backend/.env SUPABASE_JWT_SECRET." -ForegroundColor Green
}

if (-not $SkipVercel) {
    Push-Location (Join-Path $RepoRoot "apps\web")
    try {
        if (-not (Test-Path (Join-Path $RepoRoot ".vercel\project.json"))) {
            vercel link --yes --project gravitre-saas-backend 2>&1 | Out-Host
        }
        $JwtSecret | vercel env add SUPABASE_JWT_SECRET production --force 2>&1 | Out-Host
        Write-Host "Updated Vercel SUPABASE_JWT_SECRET (production)." -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

if (-not $SkipRailway) {
    if (-not $env:RAILWAY_TOKEN) {
        $env:RAILWAY_TOKEN = Read-DotEnvValue $OperatorFile "RAILWAY_TOKEN"
    }
    if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
        Write-Host "Railway CLI not installed; skipped Railway sync." -ForegroundColor Yellow
    } elseif (-not $env:RAILWAY_TOKEN) {
        Write-Host "RAILWAY_TOKEN missing; skipped Railway sync." -ForegroundColor Yellow
    } else {
        Write-Host "Setting Railway SUPABASE_JWT_SECRET on $RailwayService ..."
        railway variables set "SUPABASE_JWT_SECRET=$JwtSecret" --service $RailwayService
        Write-Host "Updated Railway SUPABASE_JWT_SECRET." -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Note: user access tokens signed with ES256 are verified via JWKS automatically." -ForegroundColor Cyan
Write-Host "Password login 400 invalid_credentials usually means wrong password OR OAuth-only account." -ForegroundColor Cyan

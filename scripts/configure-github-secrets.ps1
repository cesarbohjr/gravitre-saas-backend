#Requires -Version 5.1
<#
.SYNOPSIS
  Set GitHub Actions secrets for Auth Config Sync from local CLI credentials.

  Reads VERCEL_TOKEN from Vercel CLI auth.json, Supabase/Vercel public env from
  apps/web/.env.vercel.production (run vercel env pull first), and optional
  SUPABASE_ACCESS_TOKEN from backend/.env.operator.local.
#>
param(
    [string] $RepoRoot,
    [string] $VercelEnvFile,
    [string] $OperatorFile,
    [string] $VercelAuthFile = "$env:APPDATA\com.vercel.cli\Data\auth.json"
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
if (-not $VercelEnvFile) {
    $VercelEnvFile = Join-Path $RepoRoot "apps\web\.env.vercel.production"
}
if (-not $OperatorFile) {
    $OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"
}

function Read-DotEnvValue {
    param([string] $Path, [string] $Key)
    if (-not (Test-Path $Path)) { return $null }
    foreach ($line in Get-Content $Path) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=\s*(.+)$") {
            return $matches[1].Trim().Trim('"')
        }
    }
    return $null
}

function Set-GhSecret {
    param([string] $Name, [string] $Value)
    if (-not $Value) {
        Write-Host "  skip $Name (no value)" -ForegroundColor Yellow
        return
    }
    $Value | gh secret set $Name --repo cesarbohjr/gravitre-saas-backend
    if ($LASTEXITCODE -ne 0) { throw "gh secret set $Name failed" }
    Write-Host "  set $Name" -ForegroundColor Green
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "gh CLI not found." -ForegroundColor Red
    exit 1
}

$vercelToken = $env:VERCEL_TOKEN
if (-not $vercelToken -and (Test-Path $VercelAuthFile)) {
    $auth = Get-Content $VercelAuthFile -Raw | ConvertFrom-Json
    $vercelToken = $auth.token
}
if (-not $vercelToken) {
    Write-Host "VERCEL_TOKEN missing. Run: vercel login" -ForegroundColor Red
    exit 1
}

$supabaseToken = $env:SUPABASE_ACCESS_TOKEN
if (-not $supabaseToken) {
    $supabaseToken = Read-DotEnvValue -Path $OperatorFile -Key "SUPABASE_ACCESS_TOKEN"
}
if (-not $supabaseToken) {
    Write-Host "SUPABASE_ACCESS_TOKEN missing. Add to backend/.env.operator.local or:" -ForegroundColor Yellow
    Write-Host "  https://supabase.com/dashboard/account/tokens" -ForegroundColor Yellow
    Write-Host "Continuing without Supabase Management API secret..." -ForegroundColor Yellow
}

if (-not (Test-Path $VercelEnvFile)) {
    Write-Host "Pulling Vercel production env -> $VercelEnvFile" -ForegroundColor Cyan
    Push-Location (Join-Path $RepoRoot "apps\web")
    try {
        vercel env pull (Split-Path -Leaf $VercelEnvFile) --environment=production --yes 2>&1 | Out-Host
    } finally { Pop-Location }
}

Write-Host "Setting GitHub secrets..." -ForegroundColor Cyan
Set-GhSecret "VERCEL_TOKEN" $vercelToken
# Vercel API teamId (not slug). gravitre-ai team:
Set-GhSecret "VERCEL_ORG_ID" "team_kuQmNfrn5RtMeaWuH88LLuAf"
Set-GhSecret "SUPABASE_PROJECT_REF" "smyeexlrqdpymwjmgzqu"
if ($supabaseToken) { Set-GhSecret "SUPABASE_ACCESS_TOKEN" $supabaseToken }
Set-GhSecret "NEXT_PUBLIC_SUPABASE_URL" (Read-DotEnvValue $VercelEnvFile "NEXT_PUBLIC_SUPABASE_URL")
Set-GhSecret "NEXT_PUBLIC_SUPABASE_ANON_KEY" (Read-DotEnvValue $VercelEnvFile "NEXT_PUBLIC_SUPABASE_ANON_KEY")
Write-Host "Done." -ForegroundColor Green

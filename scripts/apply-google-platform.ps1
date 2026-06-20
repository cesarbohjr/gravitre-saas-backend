#Requires -Version 5.1
<#
.SYNOPSIS
  One-pass Google OAuth: Railway env, Supabase Google provider + URLs, gcloud APIs.

.PARAMETER ClientId
  Gravitre OAuth client ID (.apps.googleusercontent.com).

.PARAMETER ClientSecret
  Gravitre OAuth client secret (GOCSPX-...). If omitted, tries Supabase auth config.

.PARAMETER GcpProjectId
  Google Cloud project ID (default: gravitre-ai).
#>
param(
    [string] $ClientId = "1058144333767-ndsmnr5vqu6vkscfrdj3bua55434e0ns.apps.googleusercontent.com",
    [string] $ClientSecret,
    [string] $GcpProjectId = "gravitre-ai",
    [string] $ProjectRef = "smyeexlrqdpymwjmgzqu",
    [string] $ApiPublicUrl = "https://api.gravitre.app",
    [string] $AppUrl = "https://gravitre.app",
    [switch] $SkipGcloud,
    [switch] $SkipSupabase
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

function Get-SupabaseAccessToken {
    if ($env:SUPABASE_ACCESS_TOKEN) { return $env:SUPABASE_ACCESS_TOKEN.Trim() }
    if (Test-Path $OperatorFile) {
        Get-Content $OperatorFile | ForEach-Object {
            if ($_ -match '^\s*SUPABASE_ACCESS_TOKEN\s*=\s*(.+)$') {
                return $matches[1].Trim().Trim('"')
            }
        }
    }
    return $null
}

function Get-SupabaseAuthConfig {
    param([string] $Token, [string] $Ref)
    $headers = @{ Authorization = "Bearer $Token" }
    return Invoke-RestMethod -Uri "https://api.supabase.com/v1/projects/$Ref/config/auth" -Headers $headers -Method Get
}

function Set-SupabaseAuthConfig {
    param([string] $Token, [string] $Ref, [hashtable] $Body)
    $headers = @{ Authorization = "Bearer $Token" }
    $json = $Body | ConvertTo-Json -Depth 5
    Invoke-RestMethod -Uri "https://api.supabase.com/v1/projects/$Ref/config/auth" -Headers $headers -Method Patch -ContentType "application/json" -Body $json | Out-Null
}

if (-not $ClientId) {
    Write-Host "ClientId is required." -ForegroundColor Red
    exit 1
}

if ($ClientSecret -and $ClientSecret -eq $ClientId) {
    Write-Host "ClientSecret matches ClientId (likely paste error) - ignoring; will try Supabase or env." -ForegroundColor Yellow
    $ClientSecret = $null
}

$supabaseToken = Get-SupabaseAccessToken
if (-not $ClientSecret -and $supabaseToken) {
    try {
        $authCfg = Get-SupabaseAuthConfig -Token $supabaseToken -Ref $ProjectRef
        if ($authCfg.external_google_secret) {
            $ClientSecret = $authCfg.external_google_secret
            Write-Host "Using external_google_secret from Supabase auth config." -ForegroundColor Green
        }
    } catch {
        Write-Host "Could not read Supabase auth config: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

$hasSecret = [bool]$ClientSecret

Write-Host ""
Write-Host "=== 1/4 Railway + operator.local ===" -ForegroundColor Cyan
$env:GOOGLE_OAUTH_CLIENT_ID = $ClientId
if ($hasSecret) {
    $env:GOOGLE_OAUTH_CLIENT_SECRET = $ClientSecret
    & (Join-Path $RepoRoot "scripts\fill-google-operator-env.ps1") -ClientId $ClientId -ClientSecret $ClientSecret
} else {
    Write-Host "No client secret - writing Client ID only to operator.local and Railway." -ForegroundColor Yellow
    Write-Host "  Regenerate/copy GOCSPX-... from GCP (Gravitre OAuth), then re-run with -ClientSecret." -ForegroundColor Yellow
    $lines = @()
    if (Test-Path $OperatorFile) { $lines = Get-Content $OperatorFile }
    function Set-Line($c, $k, $v) {
        $found = $false; $out = @()
        foreach ($line in $c) {
            if ($line -match "^\s*$([regex]::Escape($k))\s*=") { $out += "${k}=$v"; $found = $true }
            else { $out += $line }
        }
        if (-not $found) { $out += "${k}=$v" }
        return $out
    }
    foreach ($k in @("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_ANALYTICS_CLIENT_ID")) {
        $lines = Set-Line $lines $k $ClientId
    }
    if (-not ($lines -join "`n" -match "API_PUBLIC_URL=")) { $lines += "API_PUBLIC_URL=$ApiPublicUrl" }
    Set-Content -Path $OperatorFile -Value ($lines -join "`r`n") -Encoding utf8
    if (-not $env:RAILWAY_TOKEN -and (Test-Path $OperatorFile)) {
        Get-Content $OperatorFile | ForEach-Object {
            if ($_ -match '^\s*RAILWAY_TOKEN\s*=\s*(.+)$') { $env:RAILWAY_TOKEN = $matches[1].Trim() }
        }
    }
    if ($env:RAILWAY_TOKEN) {
        railway variables set "GOOGLE_OAUTH_CLIENT_ID=$ClientId" --service gravitre-saas-backend
        railway variables set "GOOGLE_ANALYTICS_CLIENT_ID=$ClientId" --service gravitre-saas-backend
        railway variables set "API_PUBLIC_URL=$ApiPublicUrl" --service gravitre-saas-backend
    }
}

Write-Host ""
Write-Host "=== 2/4 Supabase (config push + optional Management API) ===" -ForegroundColor Cyan
Push-Location (Join-Path $RepoRoot "supabase")
try {
    supabase config push --yes 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Supabase config push OK (site_url, redirect allow list, google client_id in config.toml)." -ForegroundColor Green
    } else {
        Write-Host "Supabase config push failed (see above)." -ForegroundColor Yellow
    }
} finally { Pop-Location }

if ($hasSecret) {
    & (Join-Path $RepoRoot "scripts\configure-supabase-google.ps1") -ProjectRef $ProjectRef
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Supabase Google provider push failed (see above)." -ForegroundColor Yellow
    }
}

if ($hasSecret -and $supabaseToken -and -not $SkipSupabase) {
    $allowList = @(
        "$AppUrl/auth/callback"
        "$AppUrl/**"
        "http://localhost:3000/auth/callback"
        "http://localhost:3000/**"
    ) -join ","
    Set-SupabaseAuthConfig -Token $supabaseToken -Ref $ProjectRef -Body @{
        site_url                  = $AppUrl
        uri_allow_list            = $allowList
        external_google_enabled   = $true
        external_google_client_id = $ClientId
        external_google_secret    = $ClientSecret
    }
    Write-Host "Supabase Management API: Google secret updated." -ForegroundColor Green
} elseif (-not $hasSecret) {
    Write-Host "Supabase Google secret: set in Dashboard (Auth -> Google) or re-run with -ClientSecret GOCSPX-..." -ForegroundColor Yellow
}
Write-Host "  GCP redirect for login: https://${ProjectRef}.supabase.co/auth/v1/callback" -ForegroundColor Green

if (-not $SkipGcloud) {
    Write-Host ""
    Write-Host "=== 3/4 Google Cloud (enable APIs) ===" -ForegroundColor Cyan
    & (Join-Path $RepoRoot "scripts\configure-google-cloud.ps1") -ProjectId $GcpProjectId -ApiPublicUrl $ApiPublicUrl -SupabaseProjectRef $ProjectRef
    if ($LASTEXITCODE -ne 0) {
        Write-Host "gcloud step incomplete (login or project). Redirect URIs are on clipboard - paste into Gravitre OAuth client." -ForegroundColor Yellow
    }
} else {
    Write-Host "Skipped gcloud ( -SkipGcloud )." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 4/4 Production OAuth status ===" -ForegroundColor Cyan
& (Join-Path $RepoRoot "scripts\check-google-oauth.ps1") -ApiBase $ApiPublicUrl
exit $LASTEXITCODE

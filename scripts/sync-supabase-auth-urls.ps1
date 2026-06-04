#Requires -Version 5.1
<#
.SYNOPSIS
  Sync Supabase production auth Site URL + redirect allow list for gravitre.app OAuth.

  Requires SUPABASE_ACCESS_TOKEN (https://supabase.com/dashboard/account/tokens)
  Optional: SUPABASE_PROJECT_REF (default smyeexlrqdpymwjmgzqu)
#>
param(
    [string] $ProjectRef = "smyeexlrqdpymwjmgzqu",
    [string] $AppUrl = "https://gravitre.app"
)

$ErrorActionPreference = "Stop"

if (-not $env:SUPABASE_ACCESS_TOKEN) {
    $envFile = Join-Path (Split-Path -Parent $PSScriptRoot) "backend\.env.operator.local"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^SUPABASE_ACCESS_TOKEN=(.+)$') {
                $env:SUPABASE_ACCESS_TOKEN = $matches[1].Trim().Trim('"')
            }
        }
    }
}

if (-not $env:SUPABASE_ACCESS_TOKEN) {
    Write-Host "Set SUPABASE_ACCESS_TOKEN (Supabase account access token)." -ForegroundColor Red
    exit 1
}

$allowList = @(
    "$AppUrl/auth/callback",
    "$AppUrl/**",
    "http://localhost:3000/auth/callback",
    "http://localhost:3000/**"
) -join ","

$body = @{
    site_url = $AppUrl
    uri_allow_list = $allowList
} | ConvertTo-Json

Write-Host "Patching Supabase auth config for $ProjectRef ..."
Write-Host "  site_url=$AppUrl"

Invoke-RestMethod `
    -Method Patch `
    -Uri "https://api.supabase.com/v1/projects/$ProjectRef/config/auth" `
    -Headers @{ Authorization = "Bearer $env:SUPABASE_ACCESS_TOKEN" } `
    -ContentType "application/json" `
    -Body $body | Out-Null

Write-Host "Done. Google OAuth redirect URI (verify in Google Cloud Console):" -ForegroundColor Green
Write-Host "  https://${ProjectRef}.supabase.co/auth/v1/callback"

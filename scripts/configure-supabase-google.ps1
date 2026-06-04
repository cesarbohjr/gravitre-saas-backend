#Requires -Version 5.1
<#
.SYNOPSIS
  Enable Google OAuth on linked Supabase project via config.toml + config push.

  Reads GOOGLE_OAUTH_* from backend/.env.operator.local, writes supabase/.env
  (gitignored), then runs supabase config push.
#>
param(
    [string] $OperatorFile,
    [string] $ProjectRef = "smyeexlrqdpymwjmgzqu"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $OperatorFile) {
    $OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"
}

if (-not (Test-Path $OperatorFile)) {
    Write-Host "Missing $OperatorFile (GOOGLE_OAUTH_CLIENT_ID/SECRET)." -ForegroundColor Red
    exit 1
}

$clientId = $null
$clientSecret = $null
Get-Content $OperatorFile | ForEach-Object {
    if ($_ -match '^\s*GOOGLE_OAUTH_CLIENT_ID\s*=\s*(.+)$') { $clientId = $matches[1].Trim().Trim('"') }
    if ($_ -match '^\s*GOOGLE_OAUTH_CLIENT_SECRET\s*=\s*(.+)$') { $clientSecret = $matches[1].Trim().Trim('"') }
}

if (-not $clientId -or -not $clientSecret) {
    Write-Host "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET required in operator.local." -ForegroundColor Red
    exit 1
}

if ($clientSecret -eq $clientId) {
    Write-Host "GOOGLE_OAUTH_CLIENT_SECRET looks like a duplicate of client ID; fix operator.local." -ForegroundColor Red
    exit 1
}

$supabaseEnv = Join-Path $RepoRoot "supabase\.env"
[System.IO.File]::WriteAllText(
    $supabaseEnv,
    "GOOGLE_OAUTH_CLIENT_SECRET=$clientSecret`n",
    [System.Text.UTF8Encoding]::new($false)
)
Write-Host "Wrote supabase/.env (secret only, gitignored)." -ForegroundColor Green

Push-Location (Join-Path $RepoRoot "supabase")
try {
    Write-Host "Pushing auth.external.google to project $ProjectRef ..."
    supabase config push --yes 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "config push failed." -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "Supabase Google provider enabled (client_id + secret)." -ForegroundColor Green
    Write-Host "GCP redirect URI for login:" -ForegroundColor Cyan
    Write-Host "  https://${ProjectRef}.supabase.co/auth/v1/callback"
} finally {
    Pop-Location
}

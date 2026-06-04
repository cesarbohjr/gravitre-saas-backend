#Requires -Version 5.1
<#
.SYNOPSIS
  One-pass platform setup via CLI: Supabase Google auth, GCP, Railway, Vercel, GitHub secrets.

.PARAMETER SkipGcloud
  Skip Google Cloud API enable + redirect URI clipboard step.

.PARAMETER SkipVercelDeploy
  Skip production Vercel deploy.

.PARAMETER SkipGithubSecrets
  Skip gh secret set + Auth Config Sync workflow dispatch.

.PARAMETER SkipRailway
  Skip Railway variable push (avoids slow GraphQL when network is flaky).
#>
param(
    [switch] $SkipGcloud,
    [switch] $SkipVercelDeploy,
    [switch] $SkipGithubSecrets,
    [switch] $SkipRailway,
    [string] $GcpProjectId = "gravitre-ai"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

function Invoke-RepoScript {
    param([string] $RelativePath, [string[]] $Args = @())
    $path = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path $path)) { throw "Missing script: $path" }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $path @Args
    if ($LASTEXITCODE -ne 0) { throw "Failed: $RelativePath (exit $LASTEXITCODE)" }
}

function Test-GcloudAuth {
    $gcloud = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    if (-not (Test-Path $gcloud)) { $gcloud = "gcloud" }
    $accounts = & $gcloud auth list --format="value(account)" 2>$null
    return [bool]($accounts | Where-Object { $_ -match "@" })
}

Write-Host ""
Write-Host "=== Gravitre platform CLI apply ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "1/7 Supabase Google provider + auth URLs" -ForegroundColor Cyan
Invoke-RepoScript "scripts\configure-supabase-google.ps1"
if ($env:SUPABASE_ACCESS_TOKEN -or (Test-Path $OperatorFile)) {
    try {
        Invoke-RepoScript "scripts\sync-supabase-auth-urls.ps1"
    } catch {
        Write-Host "  sync-supabase-auth-urls skipped (needs SUPABASE_ACCESS_TOKEN in operator.local)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  sync-supabase-auth-urls skipped (add SUPABASE_ACCESS_TOKEN to operator.local for Management API)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "2/7 Google Railway + operator env" -ForegroundColor Cyan
if ($SkipRailway) {
    Write-Host "  Skipped (-SkipRailway)" -ForegroundColor Yellow
} else {
    npm run google:fill-env --silent 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "google:fill-env failed" }
    npm run google:railway --silent 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { Write-Host "  google:railway had errors (Railway API may be slow); continuing." -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "3/7 Google Cloud (APIs + redirect URIs)" -ForegroundColor Cyan
if ($SkipGcloud) {
    Write-Host "  Skipped (-SkipGcloud)" -ForegroundColor Yellow
} elseif (-not (Test-GcloudAuth)) {
    Write-Host "  gcloud not logged in. Run in this terminal:" -ForegroundColor Yellow
    Write-Host "    gcloud auth login" -ForegroundColor White
    Write-Host "  Then re-run: npm run platform:apply" -ForegroundColor Yellow
} else {
    npm run google:configure --silent 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { Write-Host "  google:configure failed; paste URIs from npm run google:setup" -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "4/7 Google OAuth health check" -ForegroundColor Cyan
npm run google:check --silent 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { throw "google:check failed" }

Write-Host ""
Write-Host "5/7 Vercel production env + deploy" -ForegroundColor Cyan
$vercelEnvFile = Join-Path $RepoRoot "apps\web\.env.vercel.production"
if (-not (Test-Path $vercelEnvFile)) {
    Push-Location (Join-Path $RepoRoot "apps\web")
    try {
        vercel env pull .env.vercel.production --environment=production --yes 2>&1 | Out-Host
    } finally { Pop-Location }
}
if (-not $SkipVercelDeploy) {
    Write-Host "  Deploying production from repo root (Vercel rootDirectory=apps/web) ..."
    Push-Location $RepoRoot
    try {
        vercel deploy --prod --yes 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "vercel deploy failed" }
    } finally { Pop-Location }
} else {
    Write-Host "  Skipped deploy (-SkipVercelDeploy)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "6/7 GitHub Actions secrets + Auth Config Sync" -ForegroundColor Cyan
if ($SkipGithubSecrets) {
    Write-Host "  Skipped (-SkipGithubSecrets)" -ForegroundColor Yellow
} else {
    Invoke-RepoScript "scripts\configure-github-secrets.ps1"
    gh workflow run auth-config-sync.yml -f skip_vercel_deploy=true 2>&1 | Out-Host
    Write-Host "  Dispatched auth-config-sync workflow (Vercel deploy skipped in CI; done locally above)." -ForegroundColor Green
}

Write-Host ""
Write-Host "7/7 Production smoke checks" -ForegroundColor Cyan
$auth = curl.exe -sI "https://gravitre.app/auth/callback?code=invalid-test" 2>&1
if ($auth -match "auth_callback_failed") {
    Write-Host "  gravitre.app/auth/callback OK (auth_callback_failed)" -ForegroundColor Green
} else {
    Write-Host "  Unexpected auth callback response:" -ForegroundColor Yellow
    $auth | Select-Object -First 5 | ForEach-Object { Write-Host "    $_" }
}

Write-Host ""
Write-Host "Platform CLI apply finished." -ForegroundColor Green
Write-Host "If gcloud was skipped: gcloud auth login && npm run google:configure" -ForegroundColor Cyan

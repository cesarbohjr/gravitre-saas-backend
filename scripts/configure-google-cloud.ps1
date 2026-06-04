#Requires -Version 5.1
<#
.SYNOPSIS
  Enable Google APIs and prepare Gravitre OAuth redirect URIs (gcloud + clipboard).

  Redirect URIs for standard OAuth web clients must be added in Google Cloud Console
  (no public API). This script enables APIs via gcloud and opens the credentials page.

.PARAMETER ProjectId
  GCP project ID. If omitted, uses gcloud config or prompts.

.PARAMETER SkipBrowser
  Do not open the Cloud Console credentials page.
#>
param(
    [string] $ProjectId = $env:GOOGLE_CLOUD_PROJECT,
    [string] $ApiPublicUrl = $(if ($env:API_PUBLIC_URL) { $env:API_PUBLIC_URL } else { "https://gravitre-saas-backend-production.up.railway.app" }),
    [string] $SupabaseProjectRef = "smyeexlrqdpymwjmgzqu",
    [switch] $SkipBrowser
)

$ErrorActionPreference = "Stop"
$gcloud = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
if (-not (Test-Path $gcloud)) {
    $gcloud = "gcloud"
}

$api = $ApiPublicUrl.TrimEnd("/")
$redirectUris = @(
    "https://${SupabaseProjectRef}.supabase.co/auth/v1/callback"
    "${api}/api/connectors/oauth/google_analytics/callback"
    "${api}/api/connectors/oauth/google_calendar/callback"
    "${api}/api/connectors/oauth/gmail/callback"
    "${api}/api/connectors/oauth/google_drive/callback"
    "${api}/api/connectors/oauth/google_docs/callback"
    "${api}/api/connectors/oauth/google_sheets/callback"
)

$services = @(
    "analyticsadmin.googleapis.com"
    "analyticsdata.googleapis.com"
    "calendar-json.googleapis.com"
    "gmail.googleapis.com"
    "drive.googleapis.com"
    "docs.googleapis.com"
    "sheets.googleapis.com"
)

Write-Host ""
Write-Host "Gravitre OAuth - Google Cloud CLI setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$authList = & $gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>&1
if ($LASTEXITCODE -ne 0 -or -not $authList) {
    Write-Host "gcloud is not logged in. Run:" -ForegroundColor Yellow
    Write-Host "  gcloud auth login" -ForegroundColor White
    Write-Host "Then re-run: npm run google:configure" -ForegroundColor Yellow
    exit 1
}
Write-Host "Account: $($authList | Select-Object -First 1)" -ForegroundColor Green

if (-not $ProjectId) {
    $ProjectId = (& $gcloud config get-value project 2>$null).Trim()
}
if (-not $ProjectId) {
    Write-Host ""
    Write-Host "Available projects:" -ForegroundColor Yellow
    & $gcloud projects list --format="table(projectId,name)"
    $ProjectId = Read-Host "Enter GCP project ID for Gravitre OAuth"
}
if (-not $ProjectId) {
    Write-Host "Project ID required." -ForegroundColor Red
    exit 1
}

& $gcloud config set project $ProjectId | Out-Null
Write-Host "Project: $ProjectId" -ForegroundColor Green

Write-Host ""
Write-Host "Enabling APIs..." -ForegroundColor Yellow
& $gcloud services enable @services --project=$ProjectId
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to enable one or more APIs." -ForegroundColor Red
    exit 1
}
Write-Host "APIs enabled." -ForegroundColor Green

$uriText = ($redirectUris -join "`r`n")
Set-Clipboard -Value $uriText
Write-Host ""
Write-Host "Copied $($redirectUris.Count) redirect URIs to clipboard:" -ForegroundColor Green
$redirectUris | ForEach-Object { Write-Host "  $_" }

Write-Host ""
Write-Host "In Google Cloud Console -> APIs & Services -> Credentials -> Gravitre OAuth:" -ForegroundColor Yellow
Write-Host "  Paste each URI under Authorized redirect URIs, then Save." -ForegroundColor Yellow

if (-not $SkipBrowser) {
    $credUrl = "https://console.cloud.google.com/apis/credentials?project=$ProjectId"
    Write-Host "Opening: $credUrl" -ForegroundColor Cyan
    Start-Process $credUrl
}

Write-Host ""
Write-Host "Next:" -ForegroundColor Cyan
Write-Host "  `$env:GOOGLE_OAUTH_CLIENT_ID = '<from-console>'"
Write-Host "  `$env:GOOGLE_OAUTH_CLIENT_SECRET = '<from-console>'"
Write-Host "  npm run google:fill-env"
Write-Host "  npm run google:railway"
Write-Host "  npm run google:check"

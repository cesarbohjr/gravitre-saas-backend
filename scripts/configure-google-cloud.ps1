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
    [string] $ApiPublicUrl = $(if ($env:API_PUBLIC_URL) { $env:API_PUBLIC_URL } else { "https://api.gravitre.app" }),
    [string] $AppPublicUrl = $(if ($env:PUBLIC_APP_URL) { $env:PUBLIC_APP_URL } else { "https://gravitre.app" }),
    [string[]] $RedirectUris,
    [string] $SupabaseProjectRef = "smyeexlrqdpymwjmgzqu",
    [switch] $SkipBrowser
)

$ErrorActionPreference = "Stop"
$gcloud = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
if (-not (Test-Path $gcloud)) {
    $gcloud = "gcloud"
}

$api = $ApiPublicUrl.TrimEnd("/")
$app = $AppPublicUrl.TrimEnd("/")
if (-not $RedirectUris -or $RedirectUris.Count -eq 0) {
    $RedirectUris = @(
        "https://${SupabaseProjectRef}.supabase.co/auth/v1/callback"
        "$app/api/connectors/oauth/google_analytics/callback"
        "$app/api/connectors/oauth/google_calendar/callback"
        "$app/api/connectors/oauth/gmail/callback"
        "$app/api/connectors/oauth/google_drive/callback"
        "$app/api/connectors/oauth/google_docs/callback"
        "$app/api/connectors/oauth/google_sheets/callback"
        "$api/api/connectors/oauth/google_analytics/callback"
        "$api/api/connectors/oauth/google_calendar/callback"
        "$api/api/connectors/oauth/gmail/callback"
        "$api/api/connectors/oauth/google_drive/callback"
        "$api/api/connectors/oauth/google_docs/callback"
        "$api/api/connectors/oauth/google_sheets/callback"
        "http://localhost:8000/api/connectors/oauth/google_analytics/callback"
    )
}

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
$gcloudReady = ($LASTEXITCODE -eq 0 -and $authList)
if (-not $gcloudReady) {
    Write-Host "gcloud not ready (run: gcloud auth login). Skipping API enable; still copying redirect URIs." -ForegroundColor Yellow
} else {
    Write-Host "Account: $($authList | Select-Object -First 1)" -ForegroundColor Green
    if (-not $ProjectId) {
        $ProjectId = (& $gcloud config get-value project 2>$null).Trim()
    }
    if ($ProjectId) {
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $gcloud config set project $ProjectId 2>&1 | Out-Null
        Write-Host "Project: $ProjectId" -ForegroundColor Green
        Write-Host ""
        Write-Host "Enabling APIs..." -ForegroundColor Yellow
        & $gcloud services enable @services --project=$ProjectId 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "API enable skipped or failed. Continuing with redirect URI list." -ForegroundColor Yellow
        } else {
            Write-Host "APIs enabled." -ForegroundColor Green
        }
        $ErrorActionPreference = $prevEap
    }
}

$uriText = ($RedirectUris -join "`r`n")
Set-Clipboard -Value $uriText
Write-Host ""
Write-Host "Copied $($RedirectUris.Count) redirect URIs to clipboard:" -ForegroundColor Green
$RedirectUris | ForEach-Object { Write-Host "  $_" }

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

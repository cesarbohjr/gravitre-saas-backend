#Requires -Version 5.1
<#
.SYNOPSIS
  Enable Google APIs and prepare Gravitre OAuth redirect URIs (gcloud + clipboard).

  Redirect URIs for standard OAuth web clients must be added in Google Cloud Console
  (no public API). This script enables APIs via gcloud and opens the credentials page.

.PARAMETER ProjectId
  GCP project ID. If omitted, uses GOOGLE_CLOUD_PROJECT, operator.local, gcloud config, or gravitre-ai.

.PARAMETER SkipBrowser
  Do not open the Cloud Console credentials page.
#>
param(
    [string] $ProjectId,
    [string] $ApiPublicUrl = $(if ($env:API_PUBLIC_URL) { $env:API_PUBLIC_URL } else { "https://gravitre-saas-backend-production.up.railway.app" }),
    [string] $SupabaseProjectRef = "smyeexlrqdpymwjmgzqu",
    [switch] $SkipBrowser
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DefaultGcpProjectId = "gravitre-ai"
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

$gcloud = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
if (-not (Test-Path $gcloud)) {
    $gcloud = "gcloud"
}

function Invoke-GcloudQuiet {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]] $Args)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $output = & $gcloud @Args 2>&1 | ForEach-Object { "$_" }
        return @{
            ExitCode = $LASTEXITCODE
            Output   = ($output -join "`n").Trim()
        }
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Read-OperatorEnvValue {
    param([string] $Key)
    if (-not (Test-Path $OperatorFile)) { return $null }
    foreach ($line in Get-Content $OperatorFile) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=\s*(.+)$") {
            return $matches[1].Trim().Trim('"')
        }
    }
    return $null
}

function Resolve-GcpProjectId {
    param([string] $ExplicitId)

    if ($ExplicitId) { return $ExplicitId.Trim() }
    if ($env:GOOGLE_CLOUD_PROJECT) { return $env:GOOGLE_CLOUD_PROJECT.Trim() }

    $fromFile = Read-OperatorEnvValue "GOOGLE_CLOUD_PROJECT"
    if ($fromFile) { return $fromFile }

    $configured = (Invoke-GcloudQuiet config get-value project).Output
    if ($configured -and $configured -ne "(unset)") { return $configured }

    $listResult = Invoke-GcloudQuiet projects list --format="value(projectId)"
    if ($listResult.ExitCode -eq 0 -and $listResult.Output) {
        $projects = $listResult.Output -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
        if ($projects -contains $DefaultGcpProjectId) { return $DefaultGcpProjectId }
        if ($projects.Count -eq 1) { return $projects[0] }
    }

    return $DefaultGcpProjectId
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

$authResult = Invoke-GcloudQuiet auth list --filter=status:ACTIVE --format="value(account)"
if ($authResult.ExitCode -ne 0 -or -not $authResult.Output) {
    Write-Host "gcloud is not logged in. Run:" -ForegroundColor Yellow
    Write-Host "  gcloud auth login" -ForegroundColor White
    Write-Host "Then re-run: npm run google:configure" -ForegroundColor Yellow
    exit 1
}
$authAccount = ($authResult.Output -split "`n" | Where-Object { $_ } | Select-Object -First 1)
Write-Host "Account: $authAccount" -ForegroundColor Green

$ProjectId = Resolve-GcpProjectId -ExplicitId $ProjectId
if (-not $ProjectId) {
    Write-Host ""
    Write-Host "Available projects:" -ForegroundColor Yellow
    Invoke-GcloudQuiet projects list --format="table(projectId,name)" | Out-Host
    $ProjectId = Read-Host "Enter GCP project ID for Gravitre OAuth"
}
if (-not $ProjectId) {
    Write-Host "Project ID required." -ForegroundColor Red
    exit 1
}

$setProject = Invoke-GcloudQuiet config set project $ProjectId
if ($setProject.ExitCode -ne 0) {
    Write-Host "Failed to set gcloud project to $ProjectId." -ForegroundColor Red
    if ($setProject.Output) { Write-Host $setProject.Output -ForegroundColor Red }
    exit 1
}
Write-Host "Project: $ProjectId" -ForegroundColor Green

Write-Host ""
Write-Host "Enabling APIs..." -ForegroundColor Yellow
$enableResult = Invoke-GcloudQuiet services enable @services --project=$ProjectId
if ($enableResult.ExitCode -ne 0) {
    Write-Host "Failed to enable one or more APIs." -ForegroundColor Red
    if ($enableResult.Output) { Write-Host $enableResult.Output -ForegroundColor Red }
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

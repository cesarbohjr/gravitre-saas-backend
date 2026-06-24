#Requires -Version 5.1
<#
.SYNOPSIS
  Apply production OAuth redirect URLs (gravitre.app + Supabase login callback).

  Automates: Supabase auth URLs, Microsoft Entra redirect URIs, HubSpot project upload,
  Google redirect URI clipboard + console open. Other vendors: console checklist.

.PARAMETER AppUrl
  Public app base (default https://gravitre.app).

.PARAMETER SupabaseProjectRef
  Supabase project ref (default smyeexlrqdpymwjmgzqu).

.PARAMETER SkipHubSpotUpload
  Patch HubSpot project files only; do not hs project upload.

.PARAMETER SkipMicrosoft
  Skip Azure AD app redirect update.
#>
param(
    [string] $AppUrl = "https://gravitre.app",
    [string] $SupabaseProjectRef = "smyeexlrqdpymwjmgzqu",
    [string] $GcpProjectId = "gravitre-ai",
    [switch] $SkipHubSpotUpload,
    [switch] $SkipMicrosoft
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"
$AppBase = $AppUrl.TrimEnd("/")

function Import-OperatorEnv {
    if (-not (Test-Path $OperatorFile)) { return @{} }
    $parsed = @{}
    Get-Content $OperatorFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $parsed[$line.Substring(0, $idx).Trim()] = $line.Substring($idx + 1).Trim().Trim('"')
    }
    foreach ($key in @("RAILWAY_TOKEN", "SUPABASE_ACCESS_TOKEN", "MICROSOFT365_CLIENT_ID")) {
        if ($parsed.ContainsKey($key) -and $parsed[$key]) {
            Set-Item -Path "Env:$key" -Value $parsed[$key]
        }
    }
    return $parsed
}

function Get-RedirectUris {
    $connectors = @(
        "hubspot", "salesforce", "quickbooks", "netsuite", "workday", "marketo",
        "jira", "confluence", "notion", "slack", "pagerduty",
        "mailchimp", "constant_contact", "xero", "airtable", "asana", "clickup",
        "freshdesk", "intercom", "monday", "github", "zendesk", "clio",
        "microsoft365",
        "google_analytics", "google_calendar", "gmail", "google_drive", "google_docs", "google_sheets"
    )
    $uris = @("https://${SupabaseProjectRef}.supabase.co/auth/v1/callback")
    foreach ($vendor in $connectors) {
        if ($vendor -eq "pagerduty") {
            $uris += "$AppBase/api/auth/callback/pagerduty"
        } elseif ($vendor -eq "clickup") {
            $uris += $AppBase
            $uris += "$AppBase/api/auth/callback/clickup"
        } else {
            $uris += "$AppBase/api/connectors/oauth/$vendor/callback"
        }
    }
    return $uris
}

function Merge-Uris {
    param([string[]] $Existing, [string[]] $Required)
    $set = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($u in ($Existing + $Required)) {
        if ($u -and $u.Trim()) { [void]$set.Add($u.Trim()) }
    }
    return @($set)
}

function Update-Microsoft365Redirects {
    param([string[]] $Uris, [string] $ClientId)
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        return @{ ok = $false; reason = "Azure CLI (az) not installed" }
    }
    $account = az account show 2>$null | ConvertFrom-Json
    if (-not $account) {
        return @{ ok = $false; reason = "Run: az login" }
    }
    $objectId = az ad app list --filter "appId eq '$ClientId'" --query "[0].id" -o tsv 2>$null
    if (-not $objectId) {
        return @{ ok = $false; reason = "No Entra app found for client id" }
    }
    $existing = az ad app show --id $objectId --query "web.redirectUris" -o json 2>$null | ConvertFrom-Json
    if (-not $existing) { $existing = @() }
    $target = $Uris | Where-Object { $_ -match "microsoft365" }
    $merged = Merge-Uris -Existing $existing -Required $target
    az ad app update --id $objectId --web-redirect-uris $merged 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        return @{ ok = $false; reason = "az ad app update failed" }
    }
    return @{ ok = $true; objectId = $objectId; count = $merged.Count }
}

function Update-GoogleRedirectClipboard {
    param([string[]] $Uris)
    & (Join-Path $RepoRoot "scripts\configure-google-cloud.ps1") `
        -ProjectId $GcpProjectId `
        -AppPublicUrl $AppBase `
        -SupabaseProjectRef $SupabaseProjectRef `
        -RedirectUris $Uris | Out-Null
    return @{ ok = $true; mode = "clipboard" }
}

$envParsed = Import-OperatorEnv
$redirectUris = Get-RedirectUris

Write-Host ""
Write-Host "=== OAuth redirect URLs ($($redirectUris.Count)) ===" -ForegroundColor Cyan
$redirectUris | ForEach-Object { Write-Host "  $_" }

Write-Host ""
Write-Host "=== 1/4 Supabase auth site URL ===" -ForegroundColor Cyan
if ($env:SUPABASE_ACCESS_TOKEN) {
    & (Join-Path $RepoRoot "scripts\sync-supabase-auth-urls.ps1") -ProjectRef $SupabaseProjectRef -AppUrl $AppBase
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        Write-Host "  Supabase sync may have failed (exit $LASTEXITCODE)" -ForegroundColor Yellow
    } else {
        Write-Host "  Supabase auth URLs updated" -ForegroundColor Green
    }
} else {
    Write-Host "  Skipped (SUPABASE_ACCESS_TOKEN missing)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 2/4 Microsoft 365 (Entra) ===" -ForegroundColor Cyan
if ($SkipMicrosoft) {
    Write-Host "  Skipped (-SkipMicrosoft)" -ForegroundColor Yellow
} elseif (-not $envParsed["MICROSOFT365_CLIENT_ID"]) {
    Write-Host "  Skipped (MICROSOFT365_CLIENT_ID missing)" -ForegroundColor Yellow
} else {
    $ms = Update-Microsoft365Redirects -Uris $redirectUris -ClientId $envParsed["MICROSOFT365_CLIENT_ID"]
    if ($ms.ok) {
        Write-Host "  Updated Entra app $($ms.objectId) ($($ms.count) redirect URIs)" -ForegroundColor Green
    } else {
        Write-Host "  $($ms.reason)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=== 3/4 HubSpot project ===" -ForegroundColor Cyan
$hsArgs = @{ ApiPublicUrl = $AppBase }
if ($SkipHubSpotUpload) { $hsArgs["SkipUpload"] = $true }
& (Join-Path $RepoRoot "scripts\setup-hubspot-app.ps1") @hsArgs
if ($LASTEXITCODE -ne 0) { Write-Host "  HubSpot setup had errors (see above)" -ForegroundColor Yellow }

Write-Host ""
Write-Host "=== 4/4 Google Cloud (Gravitre OAuth client) ===" -ForegroundColor Cyan
$googleUris = $redirectUris | Where-Object {
    ($_ -match "supabase\.co/auth/v1/callback") -or
    ($_ -match "/api/connectors/oauth/google_") -or
    ($_ -match "/api/connectors/oauth/gmail/")
}
& (Join-Path $RepoRoot "scripts\configure-google-cloud.ps1") `
    -ProjectId $GcpProjectId `
    -AppPublicUrl $AppBase `
    -SupabaseProjectRef $SupabaseProjectRef `
    -RedirectUris $googleUris
if ($LASTEXITCODE -ne 0) { Write-Host "  Google configure step incomplete" -ForegroundColor Yellow }

Write-Host ""
Write-Host "=== Manual vendor consoles (paste matching URI) ===" -ForegroundColor Cyan
$manual = @{
    "Slack API app" = ($redirectUris | Where-Object { $_ -match "slack" })
    "Salesforce Connected App" = ($redirectUris | Where-Object { $_ -match "salesforce" })
    "QuickBooks Intuit Developer" = ($redirectUris | Where-Object { $_ -match "quickbooks" })
    "NetSuite Integration" = ($redirectUris | Where-Object { $_ -match "netsuite" })
    "Workday OAuth client" = ($redirectUris | Where-Object { $_ -match "workday" })
    "Marketo LaunchPoint" = ($redirectUris | Where-Object { $_ -match "marketo" })
    "Atlassian Developer (Jira + Confluence)" = ($redirectUris | Where-Object { $_ -match "jira|confluence" })
    "Notion Integration" = ($redirectUris | Where-Object { $_ -match "notion" })
    "PagerDuty Developer App" = ($redirectUris | Where-Object { $_ -match "pagerduty" })
    "Mailchimp Developer" = ($redirectUris | Where-Object { $_ -match "mailchimp" })
    "Constant Contact Developer" = ($redirectUris | Where-Object { $_ -match "constant_contact" })
    "Xero Developer" = ($redirectUris | Where-Object { $_ -match "xero" })
    "Airtable Developer" = ($redirectUris | Where-Object { $_ -match "airtable" })
    "Asana Developer" = ($redirectUris | Where-Object { $_ -match "asana" })
    "ClickUp Developer" = ($redirectUris | Where-Object { $_ -match "clickup" })
    "Freshdesk Developer" = ($redirectUris | Where-Object { $_ -match "freshdesk" })
    "Intercom Developer" = ($redirectUris | Where-Object { $_ -match "intercom" })
    "Monday.com Developer" = ($redirectUris | Where-Object { $_ -match "monday" })
    "GitHub OAuth App" = ($redirectUris | Where-Object { $_ -match "github" })
    "Zendesk OAuth client" = ($redirectUris | Where-Object { $_ -match "zendesk" })
    "Clio Developer" = ($redirectUris | Where-Object { $_ -match "clio" })
    "Partner-gated (after approval)" = @(
        "$AppBase/api/connectors/oauth/zapier/callback",
        "$AppBase/api/connectors/oauth/hootsuite/callback",
        "$AppBase/api/connectors/oauth/gusto/callback",
        "$AppBase/api/connectors/oauth/canva/callback"
    )
}
foreach ($entry in $manual.GetEnumerator()) {
    Write-Host "  $($entry.Key): $($entry.Value)" -ForegroundColor Yellow
}

Set-Clipboard -Value ($redirectUris -join "`r`n")
Write-Host ""
Write-Host "All $($redirectUris.Count) URIs copied to clipboard." -ForegroundColor Green
Write-Host "Verify: npm run oauth:check-all" -ForegroundColor Cyan

#Requires -Version 5.1
<#
.SYNOPSIS
  Push operator env vars to Railway without overwriting CONNECTOR_SECRETS_ENCRYPTION_KEY if set.

.PARAMETER EnvFile
  Defaults to backend/.env.operator.local (gitignored).
#>
param(
    [string] $EnvFile = $(Join-Path (Split-Path -Parent $PSScriptRoot) "backend\.env.operator.local"),
    [string] $Service = "gravitre-saas-backend"
)

$ErrorActionPreference = "Stop"
$vars = @(
    "HUBSPOT_CLIENT_ID",
    "HUBSPOT_CLIENT_SECRET",
    "HUBSPOT_APP_ID",
    "HUBSPOT_DEVELOPER_API_KEY",
    "SALESFORCE_CLIENT_ID",
    "SALESFORCE_CLIENT_SECRET",
    "QUICKBOOKS_CLIENT_ID",
    "QUICKBOOKS_CLIENT_SECRET",
    "QUICKBOOKS_SANDBOX_CLIENT_ID",
    "QUICKBOOKS_SANDBOX_CLIENT_SECRET",
    "JIRA_CLIENT_ID",
    "JIRA_CLIENT_SECRET",
    "MAILCHIMP_CLIENT_ID",
    "MAILCHIMP_CLIENT_SECRET",
    "XERO_CLIENT_ID",
    "XERO_CLIENT_SECRET",
    "CLIO_CLIENT_ID",
    "CLIO_CLIENT_SECRET",
    "AIRTABLE_CLIENT_ID",
    "AIRTABLE_CLIENT_SECRET",
    "ASANA_CLIENT_ID",
    "ASANA_CLIENT_SECRET",
    "FRESHDESK_CLIENT_ID",
    "FRESHDESK_CLIENT_SECRET",
    "MICROSOFT365_CLIENT_ID",
    "MICROSOFT365_CLIENT_SECRET",
    "SLACK_CLIENT_ID",
    "SLACK_CLIENT_SECRET",
    "SLACK_APP_ID",
    "SLACK_SIGNING_SECRET",
    "PAGERDUTY_CLIENT_ID",
    "PAGERDUTY_CLIENT_SECRET",
    "NOTION_CLIENT_ID",
    "NOTION_CLIENT_SECRET",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_ANALYTICS_CLIENT_ID",
    "GOOGLE_ANALYTICS_CLIENT_SECRET",
    "CONNECTOR_SECRETS_ENCRYPTION_KEY",
    "API_PUBLIC_URL",
    "PUBLIC_APP_URL",
    "INTERNAL_API_SECRET",
    "OPENAI_API_KEY",
    "VOYAGE_API_KEY",
    "VOYAGE_EMBEDDING_ENABLED",
    "KNOWLEDGE_SYNC_INTERVAL_SECONDS",
    "ENTERPRISE_CUSTOM_DOMAIN_CNAME_TARGET",
    "DEPLOYMENT_DATA_REGION"
)

if (-not (Test-Path $EnvFile)) {
    Write-Host "Missing $EnvFile - copy backend/.env.operator.local.example" -ForegroundColor Red
    exit 1
}

$parsed = @{}
Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $idx = $line.IndexOf("=")
    if ($idx -lt 1) { return }
    $key = $line.Substring(0, $idx).Trim()
    $val = $line.Substring($idx + 1).Trim().Trim('"')
    if ($val) { $parsed[$key] = $val }
}

if (-not $env:RAILWAY_TOKEN -and $parsed.ContainsKey("RAILWAY_TOKEN")) {
    $env:RAILWAY_TOKEN = $parsed["RAILWAY_TOKEN"]
}

if ($parsed.ContainsKey("CONNECTOR_SECRETS_ENCRYPTION_KEY")) {
    $k = $parsed["CONNECTOR_SECRETS_ENCRYPTION_KEY"]
    $hex64 = "^[a-fA-F0-9]{64}$"
    if ($k -notmatch $hex64) {
        Write-Host "CONNECTOR_SECRETS_ENCRYPTION_KEY must be exactly 64 hexadecimal characters" -ForegroundColor Red
        exit 1
    }
}

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Host "Install Railway CLI: npm i -g @railway/cli" -ForegroundColor Red
    exit 1
}
if (-not $env:RAILWAY_TOKEN) {
    Write-Host "RAILWAY_TOKEN is not set. Add your Railway project token to Cursor env/secrets, or run:" -ForegroundColor Yellow
    Write-Host "  `$env:RAILWAY_TOKEN = `"<token>`"; npm run hubspot:railway" -ForegroundColor Yellow
    exit 1
}
# Project tokens do not support whoami; verify access via variables on the target service.
railway variables --service $Service 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Railway auth failed for service '$Service'. Check RAILWAY_TOKEN (Project Settings -> Tokens)." -ForegroundColor Yellow
    exit 1
}

$existingConnectorKey = $false
$listedJson = railway variables --service $Service --json 2>&1 | Out-String
if ($LASTEXITCODE -eq 0 -and $listedJson.Trim()) {
    try {
        $listed = $listedJson | ConvertFrom-Json
        if ($listed.CONNECTOR_SECRETS_ENCRYPTION_KEY) {
            $existingConnectorKey = $true
            Write-Host "CONNECTOR_SECRETS_ENCRYPTION_KEY already set on Railway - skipping (will not break existing secrets)" -ForegroundColor Yellow
        }
    } catch {
        if ($listedJson -match "CONNECTOR_SECRETS_ENCRYPTION_KEY") {
            $existingConnectorKey = $true
            Write-Host "CONNECTOR_SECRETS_ENCRYPTION_KEY already set on Railway - skipping" -ForegroundColor Yellow
        }
    }
} elseif ($listedJson -match "CONNECTOR_SECRETS_ENCRYPTION_KEY") {
    $existingConnectorKey = $true
    Write-Host "CONNECTOR_SECRETS_ENCRYPTION_KEY already set on Railway - skipping" -ForegroundColor Yellow
}

foreach ($key in $vars) {
    if (-not $parsed.ContainsKey($key)) { continue }
    if ($key -eq "CONNECTOR_SECRETS_ENCRYPTION_KEY" -and $existingConnectorKey) { continue }
    Write-Host "Setting $key..."
    railway variables set "${key}=$($parsed[$key])" --service $Service
}

Write-Host "Done." -ForegroundColor Green

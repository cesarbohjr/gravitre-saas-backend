#Requires -Version 5.1
<#
.SYNOPSIS
  Apply HubSpot + connector encryption env vars to Railway (STA-125).

.PARAMETER EnvFile
  Path to a dotenv file with HUBSPOT_* and CONNECTOR_SECRETS_ENCRYPTION_KEY (default: backend/.env.hubspot.local).

.EXAMPLE
  Copy backend/.env.hubspot.local.example to backend/.env.hubspot.local, fill values from HubSpot project Auth tab, then:
  .\scripts\apply-railway-hubspot-env.ps1
#>
param(
    [string] $EnvFile = $(Join-Path (Split-Path -Parent $PSScriptRoot) "backend\.env.hubspot.local"),
    [string] $Service = "gravitre-saas-backend-production"
)

$ErrorActionPreference = "Stop"
$vars = @(
    "HUBSPOT_CLIENT_ID",
    "HUBSPOT_CLIENT_SECRET",
    "HUBSPOT_APP_ID",
    "HUBSPOT_DEVELOPER_API_KEY",
    "CONNECTOR_SECRETS_ENCRYPTION_KEY",
    "API_PUBLIC_URL",
    "PUBLIC_APP_URL"
)

if (-not (Test-Path $EnvFile)) {
    Write-Host "Missing $EnvFile" -ForegroundColor Red
    Write-Host "Copy backend/.env.hubspot.local.example and fill Client ID/secret from:"
    Write-Host "https://app.hubspot.com/developer-projects/343328749/project/gravitre-operator"
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

$missing = $vars | Where-Object { $_ -in @("HUBSPOT_CLIENT_ID", "HUBSPOT_CLIENT_SECRET", "CONNECTOR_SECRETS_ENCRYPTION_KEY", "API_PUBLIC_URL") -and -not $parsed.ContainsKey($_) }
if ($missing.Count -gt 0) {
    Write-Host "Required keys missing in ${EnvFile}: $($missing -join ', ')" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Host "Install Railway CLI: npm i -g @railway/cli" -ForegroundColor Red
    exit 1
}

railway whoami 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Run: railway login" -ForegroundColor Yellow
    exit 1
}

foreach ($key in $vars) {
    if (-not $parsed.ContainsKey($key)) { continue }
    Write-Host "Setting $key on Railway..."
    railway variables set "${key}=$($parsed[$key])" --service $Service
}

Write-Host ""
Write-Host "Done. Verify HubSpot OAuth:" -ForegroundColor Green
Write-Host "  .\scripts\check-hubspot-oauth.ps1"
Write-Host "Then in the app: Connectors -> Connect HubSpot"

#Requires -Version 5.1
<#
.SYNOPSIS
  Bootstrap backend/.env.operator.local with production URLs (no vendor secrets).

.DESCRIPTION
  Copies .env.operator.local.example if missing, then sets API_PUBLIC_URL and
  PUBLIC_APP_URL. Optionally generates CONNECTOR_SECRETS_ENCRYPTION_KEY for local dev only.

.PARAMETER GenerateLocalEncryptionKey
  Add CONNECTOR_SECRETS_ENCRYPTION_KEY if missing (local dev only — never overwrite Railway key).
#>
param(
    [switch] $GenerateLocalEncryptionKey,
    [string] $ApiPublicUrl = "https://gravitre-saas-backend-production.up.railway.app",
    [string] $PublicAppUrl = "https://gravitre.app"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Example = Join-Path $RepoRoot "backend\.env.operator.local.example"
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not (Test-Path $OperatorFile)) {
    if (Test-Path $Example) {
        Copy-Item $Example $OperatorFile
        Write-Host "Created $OperatorFile from example" -ForegroundColor Green
    } else {
        New-Item -Path $OperatorFile -ItemType File -Force | Out-Null
        Write-Host "Created empty $OperatorFile" -ForegroundColor Green
    }
}

$lines = Get-Content $OperatorFile -ErrorAction SilentlyContinue
if (-not $lines) { $lines = @() }

function Set-EnvLine([string]$Key, [string]$Value) {
    $script:lines = $script:lines | Where-Object {
        $t = $_.Trim()
        -not ($t -and -not $t.StartsWith("#") -and $t.StartsWith("$Key="))
    }
    $script:lines += "$Key=$Value"
}

Set-EnvLine "API_PUBLIC_URL" $ApiPublicUrl
Set-EnvLine "PUBLIC_APP_URL" $PublicAppUrl
Set-EnvLine "NEXT_PUBLIC_APP_URL" $PublicAppUrl

$hasKey = $false
foreach ($line in $lines) {
    if ($line -match '^\s*CONNECTOR_SECRETS_ENCRYPTION_KEY=\s*[a-fA-F0-9]{64}\s*$') {
        $hasKey = $true
        break
    }
}

if ($GenerateLocalEncryptionKey -and -not $hasKey) {
    $keyLine = node (Join-Path $RepoRoot "backend\scripts\generate-connector-encryption-key.mjs")
    if ($keyLine -match '^CONNECTOR_SECRETS_ENCRYPTION_KEY=([a-fA-F0-9]{64})$') {
        Set-EnvLine "CONNECTOR_SECRETS_ENCRYPTION_KEY" $Matches[1]
        Write-Host "Generated local CONNECTOR_SECRETS_ENCRYPTION_KEY (dev only)" -ForegroundColor Yellow
    }
}

$lines | Set-Content $OperatorFile -Encoding utf8
Write-Host "Updated platform URLs in $OperatorFile" -ForegroundColor Green
Write-Host "  API_PUBLIC_URL=$ApiPublicUrl"
Write-Host "  PUBLIC_APP_URL=$PublicAppUrl"
Write-Host ""
Write-Host "Next: add vendor CLIENT_ID/SECRET, then: npm run hubspot:railway" -ForegroundColor Cyan

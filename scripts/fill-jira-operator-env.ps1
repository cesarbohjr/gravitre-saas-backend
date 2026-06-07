#Requires -Version 5.1
<#
.SYNOPSIS
  Merge Jira/Confluence OAuth credentials into backend/.env.operator.local and push to Railway.
#>
param(
    [string] $ClientId = $env:JIRA_CLIENT_ID,
    [string] $ClientSecret = $env:JIRA_CLIENT_SECRET,
    [string] $ConfluenceClientId = $env:CONFLUENCE_CLIENT_ID,
    [string] $ConfluenceClientSecret = $env:CONFLUENCE_CLIENT_SECRET,
    [switch] $SkipRailway
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$OperatorFile = Join-Path $RepoRoot "backend\.env.operator.local"

if (-not $ClientId -or -not $ClientSecret) {
    Write-Host "Atlassian OAuth credentials required." -ForegroundColor Yellow
    Write-Host "1. https://developer.atlassian.com/console/myapps/ -> Create OAuth 2.0 (3LO) app" -ForegroundColor Yellow
    Write-Host "2. Callback URLs:" -ForegroundColor Yellow
    Write-Host "   https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/jira/callback" -ForegroundColor White
    Write-Host "   https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/confluence/callback" -ForegroundColor White
    Write-Host "3. Run:" -ForegroundColor Yellow
    Write-Host '   $env:JIRA_CLIENT_ID="<id>"; $env:JIRA_CLIENT_SECRET="<secret>"; npm run jira:fill-env' -ForegroundColor White
    exit 1
}

& (Join-Path $RepoRoot "scripts\init-operator-platform.ps1") | Out-Null

$lines = Get-Content $OperatorFile
function Set-EnvLine([string]$Key, [string]$Value) {
    $script:lines = $script:lines | Where-Object {
        $t = $_.Trim()
        -not ($t -and -not $t.StartsWith("#") -and $t.StartsWith("$Key="))
    }
    $script:lines += "$Key=$Value"
}

Set-EnvLine "JIRA_CLIENT_ID" $ClientId
Set-EnvLine "JIRA_CLIENT_SECRET" $ClientSecret
if ($ConfluenceClientId) { Set-EnvLine "CONFLUENCE_CLIENT_ID" $ConfluenceClientId }
if ($ConfluenceClientSecret) { Set-EnvLine "CONFLUENCE_CLIENT_SECRET" $ConfluenceClientSecret }
$lines | Set-Content $OperatorFile -Encoding utf8

Write-Host "Updated $OperatorFile with Jira credentials" -ForegroundColor Green
if (-not $SkipRailway) {
    & (Join-Path $RepoRoot "scripts\apply-railway-operator-env.ps1")
}

#Requires -Version 5.1
<#
.SYNOPSIS
  Authenticate HubSpot CLI, patch Gravitre URLs, and upload integrations/hubspot-app.

.PARAMETER ApiPublicUrl
  Public API base (no trailing slash). Defaults to Railway production or $env:API_PUBLIC_URL.

.PARAMETER SkipAuth
  Skip hs account auth (use when already authenticated).

.PARAMETER SkipUpload
  Only patch config files; do not upload.
#>
param(
    [string] $ApiPublicUrl = $(if ($env:API_PUBLIC_URL) { $env:API_PUBLIC_URL } else { "https://gravitre-saas-backend-production.up.railway.app" }),
    [switch] $SkipAuth,
    [switch] $SkipUpload
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ProjectDir = Join-Path $RepoRoot "integrations\hubspot-app"
$AppMeta = Join-Path $ProjectDir "src\app\app-hsmeta.json"
$WebhooksMeta = Join-Path $ProjectDir "src\app\webhooks\webhooks-hsmeta.json"
$HsConfig = Join-Path $env:USERPROFILE ".hscli\config.yml"

function Ensure-HubSpotCli {
    if (Get-Command hs -ErrorAction SilentlyContinue) {
        $v = hs --version 2>&1 | Select-Object -First 1
        Write-Host "HubSpot CLI: $v"
        return
    }
    Write-Host "Installing @hubspot/cli globally..."
    npm install -g @hubspot/cli@latest
    if (-not (Get-Command hs -ErrorAction SilentlyContinue)) {
        throw "hs not on PATH after install. Restart the terminal and re-run this script."
    }
}

function Update-JsonUrls {
    param([string] $ApiBase)
    $oauthCallback = "$ApiBase/api/connectors/oauth/hubspot/callback"
    $webhookUrl = "$ApiBase/api/webhooks/hubspot/inbound"
    $localCallback = "http://localhost:8000/api/connectors/oauth/hubspot/callback"

    $appJson = @"
{
  "uid": "gravitre_operator_hubspot",
  "type": "app",
  "config": {
    "name": "Gravitre Operator",
    "description": "Gravitre multi-tenant HubSpot connector - OAuth CRM tools and inbound workflow triggers.",
    "distribution": "marketplace",
    "auth": {
      "type": "oauth",
      "redirectUrls": [
        "$oauthCallback",
        "$localCallback"
      ],
      "requiredScopes": [
        "crm.objects.contacts.read",
        "crm.objects.contacts.write",
        "crm.objects.deals.read",
        "crm.objects.deals.write",
        "crm.lists.read",
        "crm.lists.write",
        "oauth"
      ],
      "optionalScopes": ["automation"],
      "conditionallyRequiredScopes": []
    },
    "permittedUrls": {
      "fetch": ["https://api.hubapi.com"],
      "iframe": [],
      "img": []
    },
    "support": {
      "supportEmail": "support@gravitre.com",
      "documentationUrl": "https://github.com/gravitre/gravitre-operator-ai/blob/main/docs/integration/HUBSPOT_PLATFORM_SETUP.md",
      "supportUrl": "https://gravitre.com"
    }
  }
}
"@

    $whJson = @"
{
  "uid": "gravitre_operator_webhooks",
  "type": "webhooks",
  "config": {
    "settings": {
      "targetUrl": "$webhookUrl",
      "maxConcurrentRequests": 10
    },
    "subscriptions": {
      "legacyCrmObjects": [
        {
          "subscriptionType": "contact.creation",
          "active": true
        },
        {
          "subscriptionType": "deal.propertyChange",
          "propertyName": "dealstage",
          "active": true
        }
      ]
    }
  }
}
"@

    [System.IO.File]::WriteAllText($AppMeta, $appJson.TrimEnd() + "`n", [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText($WebhooksMeta, $whJson.TrimEnd() + "`n", [System.Text.UTF8Encoding]::new($false))

    Write-Host "Patched OAuth redirect: $oauthCallback"
    Write-Host "Patched webhook target:  $webhookUrl"
}

Ensure-HubSpotCli
Update-JsonUrls -ApiBase $ApiPublicUrl.TrimEnd("/")

if (-not $SkipAuth -and -not (Test-Path $HsConfig)) {
    $pak = $env:HUBSPOT_PERSONAL_ACCESS_KEY
    if ($pak) {
        Write-Host "Authenticating with HUBSPOT_PERSONAL_ACCESS_KEY..."
        hs account auth --personal-access-key $pak
    } else {
        Write-Host ""
        Write-Host "=== HubSpot login required (one time) ===" -ForegroundColor Yellow
        Write-Host "Create a key: https://app.hubspot.com/l/developers/keys"
        Write-Host "Non-interactive: `$env:HUBSPOT_PERSONAL_ACCESS_KEY='your-key'; .\scripts\setup-hubspot-app.ps1"
        Write-Host ""
        hs account auth
    }
}

if (-not (Test-Path $HsConfig)) {
    Write-Host ""
    Write-Host "No HubSpot CLI config at $HsConfig" -ForegroundColor Red
    Write-Host "Set HUBSPOT_PERSONAL_ACCESS_KEY and re-run, or complete: hs account auth"
    exit 1
}

if (-not $SkipUpload) {
    Write-Host ""
    Write-Host "Uploading project to HubSpot..."
    Push-Location $ProjectDir
    try {
        hs project upload
    } finally {
        Pop-Location
    }
    Write-Host ""
    Write-Host "Opening project in HubSpot..."
    Push-Location $ProjectDir
    try {
        hs project open
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "=== Next: Railway / API host env vars ===" -ForegroundColor Green
Write-Host @"

HUBSPOT_CLIENT_ID=          # App → Auth → Client ID
HUBSPOT_CLIENT_SECRET=      # App → Auth → Client secret
HUBSPOT_APP_ID=             # App overview (STA-16 webhooks)
HUBSPOT_DEVELOPER_API_KEY=  # Developer account → Keys (STA-16 only)
API_PUBLIC_URL=$($ApiPublicUrl.TrimEnd('/'))
CONNECTOR_SECRETS_ENCRYPTION_KEY=  # node backend/scripts/generate-connector-encryption-key.mjs

Template: backend/.env.hubspot.local.example
Docs:     docs/integration/HUBSPOT_PLATFORM_SETUP.md

Smoke test: Connectors → Connect HubSpot in the Gravitre app.

"@
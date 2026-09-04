# Configure Twilio platform credentials on Railway (never commit secrets).
# Usage (run locally — secrets stay in your shell, not in git):
#
#   .\scripts\configure-twilio-production.ps1 `
#     -ApiKeySid "SK..." `
#     -ApiKeySecret "..." `
#     -ConnectClientId "..." `
#     -ConnectClientSecret "..." `
#     -DefaultOrgId "<your-org-uuid>" `
#     [-AuthToken "..."] `
#     [-AccountSid "AC..."]
#
param(
  [Parameter(Mandatory = $true)][string]$ApiKeySid,
  [Parameter(Mandatory = $true)][string]$ApiKeySecret,
  [string]$AccountSid = "",
  [string]$AuthToken = "",
  [string]$ConnectClientId = "",
  [string]$ConnectClientSecret = "",
  [string]$DefaultOrgId = "",
  [string]$RailwayService = "gravitre-saas-backend"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
  Write-Error "Railway CLI not found. Install: npm i -g @railway/cli"
}

Write-Host "Setting Twilio variables on Railway service: $RailwayService (values not printed)"

railway variables --service $RailwayService set `
  "TWILIO_API_KEY_SID=$ApiKeySid" `
  "TWILIO_API_KEY_SECRET=$ApiKeySecret"

if ($AccountSid) {
  railway variables --service $RailwayService set "TWILIO_ACCOUNT_SID=$AccountSid"
}
if ($AuthToken) {
  railway variables --service $RailwayService set "TWILIO_AUTH_TOKEN=$AuthToken"
}
if ($ConnectClientId) {
  railway variables --service $RailwayService set "TWILIO_CONNECT_CLIENT_ID=$ConnectClientId"
}
if ($ConnectClientSecret) {
  railway variables --service $RailwayService set "TWILIO_CONNECT_CLIENT_SECRET=$ConnectClientSecret"
}
if ($DefaultOrgId) {
  railway variables --service $RailwayService set "TWILIO_DEFAULT_ORG_ID=$DefaultOrgId"
}

Write-Host "Done. Redeploy backend, then connect Twilio under Connectors or run verify-twilio-connector-live.py"
Write-Host "Webhook URLs to register in Twilio Console:"
Write-Host "  Voice URL (inbound): https://api.gravitre.app/api/webhooks/twilio/voice/inbound"
Write-Host "  Status callback:     https://api.gravitre.app/api/webhooks/twilio/voice/status"

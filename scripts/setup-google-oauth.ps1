#Requires -Version 5.1
<#
.SYNOPSIS
  Print Google OAuth redirect URIs and API checklist for the Gravitre OAuth client.
#>
param(
    [string] $ApiPublicUrl = $(if ($env:API_PUBLIC_URL) { $env:API_PUBLIC_URL } else { "https://gravitre-saas-backend-production.up.railway.app" }),
    [string] $AppUrl = $(if ($env:NEXT_PUBLIC_APP_URL) { $env:NEXT_PUBLIC_APP_URL } else { "https://gravitre.app" }),
    [string] $SupabaseProjectRef = "smyeexlrqdpymwjmgzqu"
)

$api = $ApiPublicUrl.TrimEnd("/")
Write-Host ""
Write-Host "Gravitre OAuth — Google Cloud Console checklist" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Authorized redirect URIs (add every line):" -ForegroundColor Yellow
Write-Host "  https://${SupabaseProjectRef}.supabase.co/auth/v1/callback"
Write-Host "  ${api}/api/connectors/oauth/google_analytics/callback"
Write-Host "  ${api}/api/connectors/oauth/google_calendar/callback"
Write-Host "  ${api}/api/connectors/oauth/gmail/callback"
Write-Host "  ${api}/api/connectors/oauth/google_drive/callback"
Write-Host "  ${api}/api/connectors/oauth/google_docs/callback"
Write-Host "  ${api}/api/connectors/oauth/google_sheets/callback"
Write-Host "  http://localhost:8000/api/connectors/oauth/google_analytics/callback"
Write-Host "  http://localhost:8000/api/connectors/oauth/google_calendar/callback"
Write-Host "  http://localhost:8000/api/connectors/oauth/gmail/callback"
Write-Host "  http://localhost:8000/api/connectors/oauth/google_drive/callback"
Write-Host "  http://localhost:8000/api/connectors/oauth/google_docs/callback"
Write-Host "  http://localhost:8000/api/connectors/oauth/google_sheets/callback"
Write-Host ""
Write-Host "Enable APIs:" -ForegroundColor Yellow
Write-Host "  - Google Analytics Admin API"
Write-Host "  - Google Analytics Data API (STA-41)"
Write-Host "  - Google Calendar API"
Write-Host "  - Gmail API"
Write-Host "  - Google Drive API"
Write-Host "  - Google Docs API"
Write-Host "  - Google Sheets API"
Write-Host ""
Write-Host "Railway env (after creating credentials):" -ForegroundColor Yellow
Write-Host "  npm run google:fill-env"
Write-Host "  npm run google:railway"
Write-Host "  npm run google:check"
Write-Host ""
Write-Host "Supabase Google provider: same Client ID/Secret as Railway GOOGLE_OAUTH_*" -ForegroundColor Yellow
Write-Host "  npm run auth:sync-urls"
Write-Host "  Site URL: $AppUrl"
Write-Host ""

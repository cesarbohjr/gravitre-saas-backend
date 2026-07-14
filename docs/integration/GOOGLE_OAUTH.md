# Google OAuth — Gravitre platform guide

One Google Cloud OAuth client (**“Gravitre OAuth”**) powers login (Supabase) and all Google connectors (Railway).

## Integration status

| Product | OAuth | Agent tools |
|---------|-------|-------------|
| **Google Analytics (GA4)** | Yes + property linking | `analytics.properties.list`, `analytics.reports.run` |
| **Google Calendar** | Yes | `calendar.freebusy`, `calendar.events.create` |
| **Gmail** | Yes | `gmail.messages.list`, `gmail.messages.get`, `gmail.messages.send` |
| **Google Drive** | Yes | `drive.files.list`, `drive.files.get` |
| **Google Docs** | Yes | `docs.documents.get` |
| **Google Sheets** | Yes | `sheets.spreadsheets.get`, `sheets.values.get` |
| **Google Search Console** | Yes + site linking | `searchconsole.sites.list`, `searchconsole.searchAnalytics.query` |
| **User login** | Supabase Auth | (not Railway) |

## Environment variables (Railway)

| Variable | Notes |
|----------|--------|
| `GOOGLE_OAUTH_CLIENT_ID` | Preferred — Gravitre OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Preferred |
| `GOOGLE_ANALYTICS_CLIENT_ID` | Alias if `GOOGLE_OAUTH_*` unset |
| `GOOGLE_ANALYTICS_CLIENT_SECRET` | Alias |
| `CONNECTOR_SECRETS_ENCRYPTION_KEY` | Required |
| `API_PUBLIC_URL` | OAuth callbacks |

## Redirect URIs (Google Cloud Console)

Production (`API_PUBLIC_URL` = Railway API host):

```
https://smyeexlrqdpymwjmgzqu.supabase.co/auth/v1/callback
https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/google_analytics/callback
https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/google_calendar/callback
https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/gmail/callback
https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/google_drive/callback
https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/google_docs/callback
https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/google_sheets/callback
https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/google_search_console/callback
```

## APIs to enable

- Google Analytics Admin API + Analytics Data API
- Google Calendar API
- Gmail API
- Google Drive API
- Google Docs API
- Google Sheets API
- **Search Console API** — required for Marketing pack GSC connector (human GCP step; see below)

## Google Search Console (Marketing #6) — human GCP checklist

**Do this in Google Cloud Console before engineering wires `google_search_console` OAuth.** Agent/Cursor has no console access.

1. Enable **Search Console API**
2. OAuth consent screen → add scope `https://www.googleapis.com/auth/webmasters.readonly`
3. OAuth client (Gravitre OAuth) → Authorized redirect URIs → add:
   ```
   https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/google_search_console/callback
   ```
4. Confirm in chat that steps 1–3 are live — connection code stays blocked until then

**Data stop-line:** raw GSC search query strings must not enter Organizational Memory / Knowledge Graph without Cesar sign-off (`docs/delivery/marketing-phase0-gsc-oauth.md`). Aggregates by URL are fine.

## CLI

```powershell
# 1) Log in to GCP (once per machine)
gcloud auth login

# 2) Enable APIs + copy redirect URIs + open Credentials page
npm run google:configure
# Optional: npm run google:configure -ProjectId your-gcp-project-id

# 3) From Gravitre OAuth client in Console (or downloaded JSON):
$env:GOOGLE_OAUTH_CLIENT_ID = "<id>.apps.googleusercontent.com"
$env:GOOGLE_OAUTH_CLIENT_SECRET = "<secret>"
# Or: npm run google:fill-env -- -ClientSecretsJsonPath "C:\path\client_secret_....json"

npm run google:fill-env
npm run google:railway
npm run auth:supabase-google   # Supabase login provider (linked CLI)
npm run google:check
```

Deploy the backend after merging Google OAuth code so production `/api/connectors/oauth/google_*` routes are active.

## Code map

| Module | Role |
|--------|------|
| `google_vendor_oauth.py` | Unified OAuth for all Google connectors |
| `google_analytics.py` | Admin + Data API |
| `google_calendar.py` | Calendar API |
| `gmail.py` | Gmail API |
| `google_drive.py` | Drive API |
| `google_docs.py` | Docs API |
| `google_sheets.py` | Sheets API |

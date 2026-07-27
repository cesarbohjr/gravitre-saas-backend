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
| **Google Ads** | Yes + customer linking + **developer token** | `googleads.campaigns.*`, `googleads.ad_groups.list`, `googleads.reports.performance`, `googleads.keywords.list` |
| **User login** | Supabase Auth | (not Railway) |

## Environment variables (Railway)

| Variable | Notes |
|----------|--------|
| `GOOGLE_OAUTH_CLIENT_ID` | Preferred — Gravitre OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Preferred |
| `GOOGLE_ANALYTICS_CLIENT_ID` | Alias if `GOOGLE_OAUTH_*` unset |
| `GOOGLE_ANALYTICS_CLIENT_SECRET` | Alias |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | **Required for Google Ads** — from Ads Manager → Tools → API Center (not the OAuth client secret) |
| `CONNECTOR_SECRETS_ENCRYPTION_KEY` | Required |
| `API_PUBLIC_URL` | OAuth callbacks |

## Redirect URIs (Google Cloud Console)

**One Google OAuth client. One connector callback.** Product (GA4 / Gmail / GSC / …) is selected at connect time and carried in signed OAuth `state` — not as separate redirect URIs.

Production (`public_app_url` = `https://gravitre.app`):

```
https://smyeexlrqdpymwjmgzqu.supabase.co/auth/v1/callback
https://gravitre.app/api/connectors/oauth/google/callback
```

That is the full connector list. Do **not** add per-product URIs (`…/google_analytics/callback`, `…/google_search_console/callback`, etc.) — they are obsolete.

Optional legacy Railway host (only if still used elsewhere): not required for connectors when `gravitre.app` is registered.

## APIs to enable

- Google Analytics Admin API + Analytics Data API
- Google Calendar API
- Gmail API
- Google Drive API
- Google Docs API
- Google Sheets API
- **Search Console API** — required for Marketing pack GSC connector (human GCP step; see below)
- **Google Ads API** — required for the Google Ads connector (human GCP + Ads Manager steps; see below)

## Google Ads — human checklist (developer token is the slow path)

**Cursor/agents cannot self-serve this.** Cesar (or an Ads admin) must complete these in Google Cloud + Google Ads Manager.

Google renamed AdWords → Google Ads in 2018; we integrate the **current Google Ads API** only (catalog key `google_ads`, UI label **Google Ads** — never “AdWords”).

1. In Google Cloud Console for the Gravitre OAuth project:
   - Enable **Google Ads API**
   - OAuth consent screen → add scope `https://www.googleapis.com/auth/adwords`
   - Keep the shared redirect URI only:
     ```
     https://gravitre.app/api/connectors/oauth/google/callback
     ```
2. In a Google Ads **Manager (MCC)** account → **Tools & settings → API Center**:
   - Apply for / copy the **Developer token**
   - Basic access may be test-only; production access often requires Google business verification (days/weeks)
3. Set Railway env: `GOOGLE_ADS_DEVELOPER_TOKEN=<token>`
4. Connect **Google Ads** on the Connectors page (OAuth), then link a customer account if prompted
5. Confirm chat when the token is live — then retry Connect Google Ads

Without the developer token, OAuth can succeed but the connector stays **Setup required** / not executable.

## Google Search Console (Marketing #6) — human GCP checklist

**Do this in Google Cloud Console before live GSC connect works.** Agent/Cursor has no console access.

1. Enable **Search Console API**
2. OAuth consent screen → add scope `https://www.googleapis.com/auth/webmasters.readonly`
3. OAuth client (Gravitre OAuth) → Authorized redirect URIs — **only** the shared connector callback (already listed above):
   ```
   https://gravitre.app/api/connectors/oauth/google/callback
   ```
   No per-product GSC URI is required.
4. If the consent screen is in **Testing**, add the connecting user (e.g. `cesar@gravitre.app`) under **Test users** — otherwise Google returns `403: access_denied` / “has not completed the Google verification process”.
5. Confirm in chat when ready — then retry Connect Search Console

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
| `google_ads.py` | Google Ads API (GAQL wrappers; no raw query injection) |
| `google_ads_oauth.py` | Ads customer linking |

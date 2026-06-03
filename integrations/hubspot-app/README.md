# Gravitre HubSpot developer project (CLI)

This folder is the **HubSpot CLI project** for Gravitre’s OAuth + webhook app. It matches `backend/app/connectors/hubspot_oauth.py` and `hubspot_webhooks.py`.

You do **not** need an MCP Auth App key.

## One-time setup (operator)

1. Install CLI (if needed): `npm install -g @hubspot/cli@latest`
2. From repo root:

   ```powershell
   .\scripts\setup-hubspot-app.ps1
   ```

3. When prompted, complete `hs account auth` in the browser (Personal Access Key from HubSpot → Development → Keys).
4. After upload, open the app in HubSpot and copy **Client ID**, **Client secret**, and **App ID** into Railway (see script output).

## URLs (edit before upload if your API host differs)

| Purpose | Path |
|--------|------|
| OAuth redirect | `{API_PUBLIC_URL}/api/connectors/oauth/hubspot/callback` |
| Webhook target | `{API_PUBLIC_URL}/api/webhooks/hubspot/inbound` |

Defaults in `app-hsmeta.json` / `webhooks-hsmeta.json` use production Railway + `localhost:8000` for OAuth.

Override for upload:

```powershell
$env:API_PUBLIC_URL = "https://api.gravitre.com"
.\scripts\setup-hubspot-app.ps1 -SkipAuth
```

## Manual CLI commands

```powershell
cd integrations/hubspot-app
hs account auth
hs project upload
hs project open
```

## Backend env vars (Railway)

See `docs/integration/HUBSPOT_PLATFORM_SETUP.md` and `backend/.env.hubspot.local.example`.

## Note on legacy vs 2026.03

Gravitre’s API still uses OAuth v1 token URL and `webhooks/v3` for programmatic subscription sync (STA-16). This CLI project is the **supported way to create a multi-account OAuth app** in 2026; webhook delivery uses the target URL above. If `ensure_app_event_subscriptions` fails after connect, configure subscriptions in the HubSpot project UI or migrate the backend to `webhooks/2026-3`.

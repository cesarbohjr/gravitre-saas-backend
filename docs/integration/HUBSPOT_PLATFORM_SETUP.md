# HubSpot platform setup (STA-125) — operator runbook

Use this when configuring **Gravitre’s** HubSpot developer app and API host env vars. Customers only use **Connectors → Connect HubSpot** in the product UI.

ChatGPT’s note about **MCP Auth Apps** is correct: do **not** use MCP Auth Apps for this integration. You do **not** need an MCP key.

HubSpot’s 2026 portal often only lets you create **multi-account OAuth apps via the CLI** (`hs project create` / upload). This repo includes a ready-made project under **`integrations/hubspot-app/`**.

### Quick start (CLI — recommended)

After upload, copy credentials into `backend/.env.hubspot.local` and push to Railway:

```powershell
npm run hubspot:open       # Auth tab → copy Client ID + secret
npm run hubspot:fill-env   # merges into .env.operator.local + pushes Railway
npm run hubspot:check      # GET /api/connectors/oauth/hubspot/status
```

Production smoke: `docs/integration/TIER1_PRODUCTION_SMOKE.md`

```powershell
# From repo root (installs CLI if missing, patches URLs, uploads project)
.\scripts\setup-hubspot-app.ps1

# Or with a custom API host:
$env:API_PUBLIC_URL = "https://api.gravitre.app"
.\scripts\setup-hubspot-app.ps1
```

1. Complete **`hs account auth`** when prompted (browser + Personal Access Key from [developer keys](https://app.hubspot.com/l/developers/keys)).
2. After **`hs project upload`**, run **`hs project open`** → copy **Client ID**, **Client secret**, **App ID** into Railway.
3. Set env vars below (including `CONNECTOR_SECRETS_ENCRYPTION_KEY`).

See **`integrations/hubspot-app/README.md`** for manual commands.

### Legacy portal (still works)

If **Legacy apps → Create app → Public** is available in your developer account, you can use that instead of the CLI. The env vars and URLs are the same.

---

## What Gravitre actually uses (from code)

| Capability | Auth | Env vars |
|------------|------|----------|
| Connect HubSpot (OAuth) | OAuth 2.0 (`/oauth/v1/token`) | `HUBSPOT_CLIENT_ID`, `HUBSPOT_CLIENT_SECRET` |
| CRM tools (contacts, deals, notes, lists) | Per-customer **access/refresh tokens** (stored encrypted) | — (no extra platform env) |
| Inbound webhooks → workflows (STA-16) | App-level webhook config + signature | `HUBSPOT_APP_ID`, `HUBSPOT_DEVELOPER_API_KEY`, `HUBSPOT_CLIENT_SECRET`, `API_PUBLIC_URL` |

### Is `HUBSPOT_DEVELOPER_API_KEY` obsolete?

**No — but only for inbound triggers (STA-16).**

- It is **not** a customer CRM API key and **not** used for normal OAuth CRM calls.
- It is HubSpot’s **Developer API key** (sent as `?hapikey=...`) to manage **app-level** webhook settings and subscriptions via `https://api.hubapi.com/webhooks/v3/{appId}/...`.
- See `backend/app/connectors/hubspot_webhooks.py` → `_developer_request()`.

If you **only** need OAuth + agent tools (no `contact.creation` / `deal.propertyChange` automations), you can ship with:

```env
HUBSPOT_CLIENT_ID=
HUBSPOT_CLIENT_SECRET=
CONNECTOR_SECRETS_ENCRYPTION_KEY=
API_PUBLIC_URL=https://api.gravitre.app
PUBLIC_APP_URL=https://gravitre.app
```

Leave `HUBSPOT_APP_ID` and `HUBSPOT_DEVELOPER_API_KEY` unset until you enable inbound triggers.

HubSpot is migrating to a newer developer platform (`2026.03` apps, newer webhook API paths). **This repo still targets legacy public apps + `webhooks/v3`.** Use **Legacy apps** in the portal until we migrate endpoints.

---

## HubSpot Developer portal (2026 UI)

1. Sign in at [developers.hubspot.com](https://developers.hubspot.com) (developer account, not a single customer portal).
2. Left nav → **Legacy apps** (not “MCP Auth Apps”).
3. **Create app** → choose **Public** (multi-account OAuth), not Private-only unless you only test in one portal.
4. Open the new app.

### Auth tab

| Gravitre env | HubSpot UI |
|--------------|------------|
| `HUBSPOT_CLIENT_ID` | Client ID |
| `HUBSPOT_CLIENT_SECRET` | Client secret |
| Redirect URL | `{API_PUBLIC_URL}/api/connectors/oauth/hubspot/callback` |

Example redirect (production):

```text
https://api.gravitre.app/api/connectors/oauth/hubspot/callback
```

**Scopes** — must match published app hsmeta **and** `hubspot_oauth.py` (`scope` vs `optional_scope`):

Required (`scope`):
- `crm.objects.contacts.read` / `crm.objects.contacts.write`
- `crm.objects.deals.read` / `crm.objects.deals.write`
- `crm.objects.companies.read`
- `crm.lists.read` / `crm.lists.write`
- `oauth`

Optional (`optional_scope` — build #8+):
- `automation`
- `crm.objects.companies.write`
- `crm.objects.owners.read`
- `tickets` (single HubSpot scope — read+write; not `crm.objects.tickets.*`)

Notes: covered by `contacts.write` (do not use `crm.objects.notes.write` — rejected by 2026 platform). Putting a required install-URL scope that the app only lists as optional causes HubSpot’s “scope mismatch” authorize error.

For webhooks, HubSpot may also require **developer/webhook-related scopes** on the app when you create subscriptions in the UI. If subscription API calls fail with a scope error, add the scopes HubSpot lists in the error (often `developers-write` / webhook-related).

### App overview

| Gravitre env | HubSpot UI |
|--------------|------------|
| `HUBSPOT_APP_ID` | App ID (numeric; also shown near app name) |

### Developer API key (STA-16 only)

| Gravitre env | Where to find it |
|--------------|------------------|
| `HUBSPOT_DEVELOPER_API_KEY` | Developer account → **Keys** (or “Developer API key” in legacy app docs). This is **not** the same as a Private App token inside a customer HubSpot account. |

Used only so the API can call:

- `PUT /webhooks/v3/{appId}/settings` (target URL)
- `POST /webhooks/v3/{appId}/subscriptions` (`contact.creation`, `deal.propertyChange` on `dealstage`)

### Webhooks tab (optional manual check)

Set **Target URL** to:

```text
{API_PUBLIC_URL}/api/webhooks/hubspot/inbound
```

Example:

```text
https://api.gravitre.app/api/webhooks/hubspot/inbound
```

On each customer **Connect HubSpot**, the backend also tries to sync this URL and subscriptions automatically (`ensure_app_event_subscriptions` in `hubspot_oauth.py`).

---

## API host environment variables

Set on the **FastAPI / Railway / Vercel backend** (not the Next.js frontend only).

```env
# Required for any HubSpot connector
HUBSPOT_CLIENT_ID=
HUBSPOT_CLIENT_SECRET=
CONNECTOR_SECRETS_ENCRYPTION_KEY=    # 64-char hex (32 bytes) — encrypts oauth_tokens in connector_secrets

# Public URLs
API_PUBLIC_URL=https://api.gravitre.app
PUBLIC_APP_URL=https://gravitre.app   # fallback for OAuth redirect if API_PUBLIC_URL unset

# Optional: separate staging HubSpot app
HUBSPOT_SANDBOX_CLIENT_ID=
HUBSPOT_SANDBOX_CLIENT_SECRET=

# Required only for inbound workflow triggers (STA-16)
HUBSPOT_APP_ID=
HUBSPOT_DEVELOPER_API_KEY=
```

Generate encryption key (64 hex chars, 32 bytes):

```bash
npm run generate:connector-key
# or: node backend/scripts/generate-connector-encryption-key.mjs
```

---

## Smoke test checklist

1. Deploy API with env vars above.
2. In Gravitre UI: **Connectors → Connect HubSpot** → complete OAuth.
3. **Tools:** run a workflow or agent step using `hubspot.contacts.search` (needs agent tool permission `hubspot:*` or read scopes).
4. **Triggers (if STA-16 configured):** in HubSpot, create a contact; confirm `POST /api/webhooks/hubspot/inbound` receives payload and a workflow run is created (check `workflow_runs.trigger_type = hubspot`).

---

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Created an **MCP Auth App** | Use **Legacy apps → Public** instead |
| Used a **Private App token** as `HUBSPOT_DEVELOPER_API_KEY` | Use **Developer API key** from developer account Keys |
| Redirect URL points at frontend only | Must hit **API** callback path `/api/connectors/oauth/hubspot/callback` |
| Missing `CONNECTOR_SECRETS_ENCRYPTION_KEY` | OAuth completes but tokens cannot be stored |
| `API_PUBLIC_URL` is HTTP or localhost in production | HubSpot webhooks require HTTPS public URL |

---

## Code references

- OAuth: `backend/app/connectors/hubspot_oauth.py`
- CRM API: `backend/app/connectors/hubspot.py`
- Webhooks: `backend/app/connectors/hubspot_webhooks.py`
- Inbound route: `backend/app/routers/webhooks/hubspot_inbound.py`
- Connect UI OAuth start: `backend/app/routers/connector_oauth.py`

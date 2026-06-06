# Connector platform (Tier 1+)

All integrations share one connect flow. Use these building blocks when adding a new vendor.

## Backend

| Module | Responsibility |
|--------|----------------|
| `app/connectors/platform.py` | OAuth row reuse, `pending_auth`, API key storage (`connector_secrets`) |
| `app/routers/connector_oauth.py` | `POST /api/connectors/oauth/{provider}/start`, `GET .../callback` |
| `app/routers/connectors.py` | CRUD, test, sync, delete (`POST .../delete`) |
| `app/workflows/audit.py` | Non-blocking audit (never fails connect/delete) |

### Adding OAuth (Tier 2+ pattern)

1. Add `{vendor}_oauth.py` with `*_oauth_configured`, `*_authorize_url`, `complete_*_oauth_connection`.
2. Register vendor in `SUPPORTED_OAUTH_PROVIDERS` and `start_oauth` / `oauth_callback` branches.
3. Add docs URL to `platform.OAUTH_DOCS_URLS`.
4. Set Railway env: `{VENDOR}_CLIENT_ID`, `{VENDOR}_CLIENT_SECRET`, redirect `{API_PUBLIC_URL}/api/connectors/oauth/{vendor}/callback`.
5. Add UI entry in `apps/web/lib/connectors.ts` (`SHIPPED_OAUTH_CONNECTOR_TYPES`) and connector catalog.

OAuth start **reuses** existing rows by `(org_id, name)` or `(org_id, vendor)` — no duplicate inserts.

### Adding API key connectors

1. Add vendor to `ALLOWED_CONNECTOR_VENDORS`.
2. Store secrets via `store_connector_api_key()` → `connector_secrets` (uses `CONNECTOR_SECRETS_ENCRYPTION_KEY`).
3. Frontend: `authType: "apiKey"` in catalog; send `apiKey` in create/update body.

Zendesk/GitHub use `secrets` map; Stripe uses `apiKey`.

## Frontend

| Module | Responsibility |
|--------|----------------|
| `apps/web/lib/connectors.ts` | Vendor key mapping, shipped OAuth list |
| `apps/web/lib/api.ts` | `connectorsApi.startOAuth`, `reconnectOAuth`, `delete` |
| `apps/web/app/api/connectors/**` | Proxies to FastAPI |

OAuth connectors: **Complete OAuth** (not API key in Configure).

## Shipped integrations

**Tier 1:** HubSpot, Zendesk, GitHub, Google Calendar  
**Tier 2:** Salesforce, QuickBooks, Stripe (API key), Jira, Confluence, PagerDuty, Notion, Google Analytics (+ Gmail/Drive/Docs/Sheets via Google OAuth)

## Production checks

- `GET /api/connectors/oauth/{provider}/status` → `configured: true`, `encryptionConfigured: true`
- Connect → provider consent → `/connectors?oauth=success`
- Test connection passes; delete with name confirmation works

See `TIER1_PRODUCTION_SMOKE.md` and `TIER2_PRODUCTION_SMOKE.md`.

## Partner connectors (Tier 3+)

Third-party packages use the Connector SDK: `docs/integration/connector-sdk-spec.md`.

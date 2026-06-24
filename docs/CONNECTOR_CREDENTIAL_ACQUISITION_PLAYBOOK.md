# Gravitre Connector Credential Acquisition Playbook

**Version:** 1.0  
**Audience:** Platform operators, DevOps, integration engineers  
**Goal:** Obtain every credential required for one-click OAuth or secure API-key connect.

**Production URLs (current):**
- API: `https://gravitre-saas-backend-production.up.railway.app`
- Frontend: `https://gravitre.app`

---

## Before You Start

### Global platform variables (required for any connector)

```env
CONNECTOR_SECRETS_ENCRYPTION_KEY=   # 64 hex chars — backend/scripts/generate-connector-encryption-key.mjs
API_PUBLIC_URL=https://gravitre-saas-backend-production.up.railway.app
NEXT_PUBLIC_APP_URL=https://gravitre.app
```

Set these in **Railway** (backend) and **Vercel** (frontend) before testing OAuth.

### OAuth callback pattern

Every platform OAuth app registers:

```
{API_PUBLIC_URL}/api/connectors/oauth/{vendor}/callback
```

Customer flow (HubSpot gold standard — see Section 7 in `CONNECTOR_PRODUCTION_READINESS_REPORT.md`):

```
Connect → /api/connectors/oauth/{vendor}/start → Vendor consent → callback → encrypted tokens → tools
```

---

## Section 7 — HubSpot Gold Standard (operator playbook)

### Why HubSpot is true one-click

| Layer | Implementation |
|-------|----------------|
| Platform app | `HUBSPOT_CLIENT_ID` + `HUBSPOT_CLIENT_SECRET` in Railway |
| OAuth routes | `backend/app/connectors/hubspot_oauth.py`, `connector_oauth.py` |
| Token storage | Encrypted in `connector_secrets` via `CONNECTOR_SECRETS_ENCRYPTION_KEY` |
| Refresh | `ensure_hubspot_access_token()` before every API call |
| Tools | 10 actions in `tool_service.py` (contacts, deals, notes, lists, sequences) |
| Customer UX | Connectors UI → Connect → consent → active connector |

### Official portal

- Developer account: [developers.hubspot.com](https://developers.hubspot.com)
- **Use Legacy apps → Public app** (not MCP Auth Apps)
- CLI path: `integrations/hubspot-app/` — see `docs/integration/HUBSPOT_PLATFORM_SETUP.md`

### Click-by-click

1. Sign in at [developers.hubspot.com](https://developers.hubspot.com).
2. **Legacy apps** → **Create app** → **Public** (multi-account OAuth).
3. **Auth** tab:
   - Redirect URL: `https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/hubspot/callback`
   - Scopes: `crm.objects.contacts.read/write`, `crm.objects.deals.read/write`, `crm.objects.notes.write`, `crm.lists.read/write`, `automation` (sequences)
4. Copy **Client ID** and **Client secret** → Railway:
   ```env
   HUBSPOT_CLIENT_ID=
   HUBSPOT_CLIENT_SECRET=
   ```
5. (Optional webhooks) Copy **App ID** + [Developer API key](https://app.hubspot.com/l/developers/keys):
   ```env
   HUBSPOT_APP_ID=
   HUBSPOT_DEVELOPER_API_KEY=
   ```
6. Deploy backend; verify: `GET /api/connectors/oauth/hubspot/status` (or `npm run hubspot:check`).
7. In product: **Connectors → HubSpot → Connect** → complete consent in test portal.

### Sandbox

- Optional separate app: `HUBSPOT_SANDBOX_CLIENT_ID`, `HUBSPOT_SANDBOX_CLIENT_SECRET`
- Use HubSpot developer test account portals

### Common failures

| Failure | Fix |
|---------|-----|
| Redirect URI mismatch | Exact match including `https`, no trailing slash mismatch |
| Invalid scopes | Re-authorize after adding scopes in app settings |
| Private app only | Must be **Public** for multi-customer OAuth |
| Token refresh errors | Check `CONNECTOR_SECRETS_ENCRYPTION_KEY` stable across deploys |

### Time estimate

2–4 hours first time (including HubSpot developer account + Railway env).

### E2E test

1. Connect HubSpot from UI  
2. Confirm connector `status: active`  
3. Run workflow or agent with `hubspot.contacts.search`  
4. Revoke/reconnect to test refresh  

---

## Tier 1–3 OAuth playbooks

### Salesforce

| Item | Value |
|------|-------|
| Portal | [developer.salesforce.com](https://developer.salesforce.com) → Setup → App Manager |
| App type | **Connected App** (OAuth 2.0 Web Server Flow) |
| Redirect | `.../api/connectors/oauth/salesforce/callback` |
| Env | `SALESFORCE_CLIENT_ID`, `SALESFORCE_CLIENT_SECRET` |
| Scopes | `api`, `refresh_token`, `offline_access` + object permissions |
| Sandbox | Separate Connected App → `SALESFORCE_SANDBOX_*` |
| Docs | [Connected App basics](https://help.salesforce.com/s/articleView?id=sf.connected_app_create.htm) |

**Setup:** App Manager → New Connected App → Enable OAuth → paste callback → assign profiles → copy Consumer Key/Secret.

---

### QuickBooks Online (Intuit)

| Item | Value |
|------|-------|
| Portal | [developer.intuit.com](https://developer.intuit.com) |
| App type | QuickBooks Online **OAuth 2.0** app |
| Redirect | `.../api/connectors/oauth/quickbooks/callback` |
| Env | `QUICKBOOKS_CLIENT_ID`, `QUICKBOOKS_CLIENT_SECRET` |
| Scopes | `com.intuit.quickbooks.accounting` |
| Sandbox | Intuit sandbox company + sandbox keys |
| Docs | [Intuit OAuth 2.0](https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0) |

---

### NetSuite

| Item | Value |
|------|-------|
| Portal | NetSuite → Setup → Integration → Manage Integrations |
| App type | **OAuth 2.0** integration record |
| Redirect | `.../api/connectors/oauth/netsuite/callback` |
| Env | `NETSUITE_CLIENT_ID`, `NETSUITE_CLIENT_SECRET` |
| Notes | Account ID required; Token-Based Auth / OAuth 2.0 per Oracle docs |
| Docs | [NetSuite OAuth 2.0](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_1540391670.html) |

---

### Workday

| Item | Value |
|------|-------|
| Portal | Workday developer / customer tenant |
| App type | **API Client** / ISU with OAuth 2.0 |
| Redirect | `.../api/connectors/oauth/workday/callback` |
| Env | `WORKDAY_CLIENT_ID`, `WORKDAY_CLIENT_SECRET` |
| Customer fields | Tenant URL (e.g. `https://wd2-impl.workday.com/...`) |
| Docs | [Workday REST](https://community.workday.com/sites/default/files/file-hosting/restapi/index.html) |

---

### Marketo (Adobe)

| Item | Value |
|------|-------|
| Portal | [developers.marketo.com](https://developers.marketo.com) |
| App type | LaunchPoint / REST API service (custom OAuth) |
| Redirect | `.../api/connectors/oauth/marketo/callback` |
| Env | `MARKETO_CLIENT_ID`, `MARKETO_CLIENT_SECRET` (often per customer munchkin) |
| Customer fields | Munchkin ID |
| Docs | [Marketo REST authentication](https://developers.marketo.com/rest-api/authentication/) |

---

### Jira & Confluence (Atlassian)

| Item | Value |
|------|-------|
| Portal | [developer.atlassian.com/console/myapps/](https://developer.atlassian.com/console/myapps/) |
| App type | **OAuth 2.0 (3LO)** integration |
| Redirects | `.../jira/callback` and `.../confluence/callback` |
| Env | `JIRA_CLIENT_ID`, `JIRA_CLIENT_SECRET` (Confluence can share) |
| Scopes | Jira: `read:jira-work`, `write:jira-work`; Confluence: `read:confluence-content.all`, `write:confluence-content` |
| Docs | [Atlassian OAuth 2.0](https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/) |

---

### PagerDuty

| Item | Value |
|------|-------|
| Portal | [developer.pagerduty.com](https://developer.pagerduty.com) |
| App type | OAuth 2.0 app |
| Redirect | `.../api/connectors/oauth/pagerduty/callback` |
| Env | `PAGERDUTY_CLIENT_ID`, `PAGERDUTY_CLIENT_SECRET` |
| Docs | [PagerDuty API OAuth](https://developer.pagerduty.com/docs/oauth/overview) |

---

### Notion

| Item | Value |
|------|-------|
| Portal | [notion.so/my-integrations](https://www.notion.so/my-integrations) → **Public** integration |
| App type | Notion OAuth integration |
| Redirect | `.../api/connectors/oauth/notion/callback` |
| Env | `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET` |
| Docs | [Notion authorization](https://developers.notion.com/docs/authorization) |

---

### Google Workspace (shared OAuth app)

| Item | Value |
|------|-------|
| Portal | [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials |
| App type | **OAuth 2.0 Client ID** (Web application) |
| Env | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` |
| Redirects (all on same client) | See matrix in `CONNECTOR_IMPLEMENTATION_MATRIX.md` |
| Enable APIs | Analytics Data API, Calendar API, Gmail API, Drive API, Docs API, Sheets API |
| Scopes | Per product — see `docs/integration/GOOGLE_OAUTH.md` |
| Docs | [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2) |

**Verification:** Google Cloud → OAuth consent screen → **Published** (or test users for dev).

---

### Slack (current: NOT platform OAuth)

> **Architecture note:** Gravitre catalog labels Slack as OAuth, but **no `/api/connectors/oauth/slack` route exists**. Today customers paste a **Bot User OAuth Token** (`xoxb-`).

| Item | Value |
|------|-------|
| Portal | [api.slack.com/apps](https://api.slack.com/apps) |
| To enable one-click | Create Slack app → OAuth & Permissions → `chat:write`, `channels:read` → implement `slack_oauth.py` (engineering) |
| Current env | `SLACK_SIGNING_SECRET` (slash commands only) |
| Customer field | Bot token stored encrypted per connector |
| Docs | [Slack OAuth](https://api.slack.com/authentication/oauth-v2) |

---

### Microsoft Teams (not implemented)

Use **Microsoft 365** Graph OAuth (`MICROSOFT365_CLIENT_ID`) for mail/calendar/Teams messaging. Dedicated Teams OAuth is **not** in `SUPPORTED_OAUTH_PROVIDERS`.

| Portal | [entra.microsoft.com](https://entra.microsoft.com) → App registrations |
| App type | Multitenant **Web** app |
| Redirect | `.../api/connectors/oauth/microsoft365/callback` |
| Admin consent | Often required for org-wide deploy |

---

## Generic OAuth playbooks (pattern)

For vendors in `GENERIC_OAUTH_VENDORS` (`oauth_provider_registry.py`):

1. Create developer account at vendor portal (link in matrix).
2. Create **OAuth 2.0 Web Application** (authorization code grant).
3. Register redirect: `https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/{vendor}/callback`
4. Set Railway env: `{VENDOR_UPPER}_CLIENT_ID`, `{VENDOR_UPPER}_CLIENT_SECRET`
5. If **PKCE** (Salesforce, Airtable, Canva, Xero): enable PKCE in vendor portal — Gravitre sends `code_challenge` automatically.
6. If **subdomain** (Freshdesk, Zendesk OAuth): customer enters subdomain at connect time.
7. Deploy → test Connect from UI.

### Per-vendor portal links

| Vendor | Developer portal |
|--------|------------------|
| Zapier | [platform.zapier.com](https://platform.zapier.com) — **partner required** |
| Mailchimp | [mailchimp.com/developer](https://mailchimp.com/developer/) |
| Constant Contact | [developer.constantcontact.com](https://developer.constantcontact.com) |
| Hootsuite | [developer.hootsuite.com](https://developer.hootsuite.com) — **approval required** |
| Xero | [developer.xero.com](https://developer.xero.com) — PKCE |
| Airtable | [airtable.com/developers](https://airtable.com/developers) — PKCE |
| Asana | [developers.asana.com](https://developers.asana.com) |
| ClickUp | [clickup.com/api](https://clickup.com/api) |
| Freshdesk | [developers.freshdesk.com](https://developers.freshdesk.com) |
| Intercom | [developers.intercom.com](https://developers.intercom.com) |
| Monday.com | [developer.monday.com](https://developer.monday.com) |
| Microsoft 365 | [entra.microsoft.com](https://entra.microsoft.com) |
| Odoo | [odoo.com/documentation](https://www.odoo.com/documentation) — **API key** (no platform OAuth app); customer URL + username + key |
| GitHub | [github.com/settings/developers](https://github.com/settings/developers) — OAuth App |
| Zendesk | Admin → Apps and integrations → APIs → OAuth clients |
| Canva | [canva.dev](https://www.canva.dev) — PKCE + **partner** |
| Gusto | [docs.gusto.com/app-integrations](https://docs.gusto.com/app-integrations) — **partner** |

---

## API key connectors (Pattern B)

**No platform OAuth.** Customer pastes credentials in Connectors UI; stored encrypted per org.

| Vendor | Where to get key | Customer fields | Minimum permissions |
|--------|------------------|-----------------|---------------------|
| Segment | Segment → Sources → HTTP API → Write key | Write key | Track, identify |
| LinkedIn | LinkedIn Developer → Marketing API | Access token | Ads / lead gen (per ADR) |
| Stripe | Stripe Dashboard → Developers → API keys | Secret key (`sk_`) | Restricted key: read invoices/subscriptions |
| Mixpanel | Project Settings → Access keys | Project token / service account | Query + export |
| SEMrush | [semrush.com/api](https://www.semrush.com/api/) | API key | Analytics units |
| StackAdapt | StackAdapt support / API docs | API token | Campaign read |
| Apollo | Apollo → Settings → API | API key | People search |
| SendGrid | SendGrid → Settings → API Keys | API key | Mail send |
| Twilio | Twilio Console | Account SID + Auth Token | SMS send |
| n8n | n8n instance → API | API key + base URL | Workflow execute |
| Motion | Motion API settings | API key | Tasks read/write |
| BambooHR | BambooHR → API key | API key + subdomain | Employee read |
| Absorb LMS | Absorb admin → API | API key + portal URL | Courses, enrollments |
| Gorgias | Gorgias → REST API | API key + subdomain | Tickets |
| Snowflake | Snowflake admin | Password or key-pair + account locator | SQL execute (scoped role) |
| ADP | ADP Marketplace partner | Partner credentials | **Partner only** |

---

## Database & IAM

| Vendor | Credentials | Notes |
|--------|-------------|-------|
| PostgreSQL | Connection string | `postgresql://user:pass@host:5432/db?sslmode=require` |
| MongoDB | Atlas connection string | SRV URI with user/password |
| AWS S3 | IAM access key + secret + region + bucket | Least-privilege `s3:GetObject`, `PutObject` on prefix |

---

## Plaid (Pattern D)

| Item | Value |
|------|-------|
| Portal | [dashboard.plaid.com](https://dashboard.plaid.com) |
| Env | `PLAID_CLIENT_ID`, `PLAID_SECRET` |
| Flow | **Plaid Link** (frontend) → `public_token` → backend exchange |
| Not OAuth | Do not register `/api/connectors/oauth/plaid/callback` |
| Docs | [Plaid Link](https://plaid.com/docs/link/) |

---

## Section 8 — Platform `.env` template

Copy to Railway backend. **Only legitimate platform variables** — no fake OAuth for API-key vendors.

```env
# === Core (required) ===
CONNECTOR_SECRETS_ENCRYPTION_KEY=
API_PUBLIC_URL=https://gravitre-saas-backend-production.up.railway.app
NEXT_PUBLIC_APP_URL=https://gravitre.app

# === Tier 1–3 OAuth ===
HUBSPOT_CLIENT_ID=
HUBSPOT_CLIENT_SECRET=
# HUBSPOT_SANDBOX_CLIENT_ID=
# HUBSPOT_SANDBOX_CLIENT_SECRET=
# HUBSPOT_APP_ID=
# HUBSPOT_DEVELOPER_API_KEY=

SALESFORCE_CLIENT_ID=
SALESFORCE_CLIENT_SECRET=
# SALESFORCE_SANDBOX_CLIENT_ID=
# SALESFORCE_SANDBOX_CLIENT_SECRET=

QUICKBOOKS_CLIENT_ID=
QUICKBOOKS_CLIENT_SECRET=

NETSUITE_CLIENT_ID=
NETSUITE_CLIENT_SECRET=

WORKDAY_CLIENT_ID=
WORKDAY_CLIENT_SECRET=

MARKETO_CLIENT_ID=
MARKETO_CLIENT_SECRET=

JIRA_CLIENT_ID=
JIRA_CLIENT_SECRET=
# CONFLUENCE_CLIENT_ID=
# CONFLUENCE_CLIENT_SECRET=

PAGERDUTY_CLIENT_ID=
PAGERDUTY_CLIENT_SECRET=

NOTION_CLIENT_ID=
NOTION_CLIENT_SECRET=

# === Google (shared — 6 products) ===
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=

# === Generic OAuth ===
ZAPIER_CLIENT_ID=
ZAPIER_CLIENT_SECRET=
MAILCHIMP_CLIENT_ID=
MAILCHIMP_CLIENT_SECRET=
CONSTANT_CONTACT_CLIENT_ID=
CONSTANT_CONTACT_CLIENT_SECRET=
HOOTSUITE_CLIENT_ID=
HOOTSUITE_CLIENT_SECRET=
XERO_CLIENT_ID=
XERO_CLIENT_SECRET=
AIRTABLE_CLIENT_ID=
AIRTABLE_CLIENT_SECRET=
ASANA_CLIENT_ID=
ASANA_CLIENT_SECRET=
CLICKUP_CLIENT_ID=
CLICKUP_CLIENT_SECRET=
FRESHDESK_CLIENT_ID=
FRESHDESK_CLIENT_SECRET=
INTERCOM_CLIENT_ID=
INTERCOM_CLIENT_SECRET=
MONDAY_CLIENT_ID=
MONDAY_CLIENT_SECRET=
GUSTO_CLIENT_ID=
GUSTO_CLIENT_SECRET=
CANVA_CLIENT_ID=
CANVA_CLIENT_SECRET=
MICROSOFT365_CLIENT_ID=
MICROSOFT365_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
ZENDESK_CLIENT_ID=
ZENDESK_CLIENT_SECRET=

# === Plaid Link ===
PLAID_CLIENT_ID=
PLAID_SECRET=

# === Slack (signing only today; bot token per connector) ===
SLACK_SIGNING_SECRET=

# === Platform AI (NOT connectors) ===
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

---

## Partner-gated connectors

Do **not** promise one-click connect until partner approval:

- **Zapier** — [Zapier Platform Partner](https://platform.zapier.com)
- **Hootsuite** — Developer program approval
- **Gusto** — [Gusto App Integrations](https://docs.gusto.com/app-integrations)
- **Canva** — [Canva Connect](https://www.canva.dev/docs/connect/)
- **ADP** — ADP Marketplace partner
- **Workday / NetSuite / Marketo** — enterprise customer-specific apps may be required at scale

---

## References

- `backend/.env.example`
- `docs/CONNECTOR_AUTH_PRODUCTION_READINESS.md`
- `docs/integration/HUBSPOT_PLATFORM_SETUP.md`
- `docs/integration/GOOGLE_OAUTH.md`
- Vendor docs linked in tables above

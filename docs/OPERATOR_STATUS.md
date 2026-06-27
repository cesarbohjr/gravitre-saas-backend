# Gravitre Operator Status

**Last run:** May 29, 2026  
**API:** `https://gravitre-saas-backend-production.up.railway.app`  
**App:** `https://gravitre.app`

Run live checks anytime:

```powershell
npm run oauth:check-all
npm run hubspot:check
npm run google:check
```

Bootstrap local operator file (URLs only, no secrets):

```powershell
npm run operator:init
```

Push credentials to Railway (requires `RAILWAY_TOKEN` or `railway login`):

```powershell
npm run hubspot:railway
```

---

## Global platform variables

| Variable | Vercel production | Railway production |
|----------|-------------------|-------------------|
| `API_PUBLIC_URL` | Set | Set (via checks) |
| `NEXT_PUBLIC_APP_URL` | `https://gravitre.app` | N/A |
| `FASTAPI_BASE_URL` | `https://gravitre-saas-backend-production.up.railway.app` | N/A |
| `CONNECTOR_SECRETS_ENCRYPTION_KEY` | N/A | **Set** (`encryptionConfigured: true`) |

---

## OAuth readiness (production API)

### Ready — one-click connect works today

| Vendor | Check command |
|--------|---------------|
| HubSpot | `npm run hubspot:check` |
| Salesforce | `GET .../salesforce/status` |
| QuickBooks | `npm run quickbooks:check` |
| PagerDuty | `npm run pagerduty:check` |
| Notion | `GET .../notion/status` |
| Google Analytics | `npm run google:check` |
| Google Calendar | `npm run google:check` |
| Gmail | `npm run google:check` |
| Google Drive | `npm run google:check` |
| Google Docs | `npm run google:check` |
| Google Sheets | `npm run google:check` |

**Customer action:** Log in → [Connectors](https://gravitre.app/connectors) → Connect.

### Not configured — add platform env vars

| Vendor | Env vars | Fill script |
|--------|----------|-------------|
| Jira | `JIRA_CLIENT_ID`, `JIRA_CLIENT_SECRET` | `npm run jira:fill-env` |
| Confluence | `CONFLUENCE_CLIENT_*` (or share Jira app) | `npm run jira:fill-env` |
| NetSuite | `NETSUITE_CLIENT_ID`, `NETSUITE_CLIENT_SECRET` | Manual → `hubspot:railway` |
| Workday | `WORKDAY_CLIENT_ID`, `WORKDAY_CLIENT_SECRET` | Manual → `hubspot:railway` |
| Marketo | `MARKETO_CLIENT_ID`, `MARKETO_CLIENT_SECRET` | Manual → `hubspot:railway` |

### Generic OAuth — deploy latest backend first

Mailchimp, Asana, Xero, GitHub OAuth, etc. return `Unsupported OAuth provider` on **current production deploy** (`18c67cc`). Local `main` includes `generic_oauth.py` and `oauth_provider_registry.py` but they are **not deployed yet**.

**Action:** Commit + push backend → Railway redeploy, then register generic OAuth apps and set `{VENDOR}_CLIENT_ID/SECRET`.

### API key connectors (no platform OAuth)

Zendesk, GitHub (PAT), Segment, Stripe, LinkedIn — customer enters credentials in Connectors UI.

### Slack gap

Slack uses **OAuth v2** (`slack_oauth.py` + `SLACK_CLIENT_ID/SECRET`). See Connectors → Slack.

---

## Your immediate checklist

- [x] Verify `API_PUBLIC_URL` / `NEXT_PUBLIC_APP_URL` on Vercel
- [x] Verify `CONNECTOR_SECRETS_ENCRYPTION_KEY` on Railway
- [x] HubSpot, Salesforce, QuickBooks, Google, PagerDuty, Notion ready
- [ ] Register Atlassian app → `npm run jira:fill-env` → `npm run hubspot:railway`
- [ ] Deploy latest backend for generic OAuth vendors
- [ ] Smoke test: connect HubSpot at https://gravitre.app/connectors

---

## Reference

- `backend/.env.operator.local.example` — credential template
- `docs/CONNECTOR_CREDENTIAL_ACQUISITION_PLAYBOOK.md` — vendor playbooks
- `docs/integration/TIER1_PRODUCTION_SMOKE.md` — smoke test checklist

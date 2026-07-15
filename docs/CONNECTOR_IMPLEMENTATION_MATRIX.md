# Gravitre Connector Implementation Matrix

**Version:** 1.0  
**Last audited:** May 29, 2026  
**Code references:** `backend/app/routers/connector_oauth.py`, `backend/app/connectors/oauth_provider_registry.py`, `apps/web/lib/connectors.ts`, `backend/app/connectors/action_catalog/`

**Production API:** `https://gravitre-saas-backend-production.up.railway.app`  
**Production frontend:** `https://gravitre.app`

---

## Section 1 — Master Connector Matrix

| Vendor | Auth Type | Platform Env Vars | Customer Fields | Redirect URI | PKCE | Partner Approval | Production Ready |
|--------|-----------|-------------------|-----------------|--------------|------|------------------|------------------|
| HubSpot | Platform OAuth | `HUBSPOT_CLIENT_ID`, `HUBSPOT_CLIENT_SECRET` (+ optional `HUBSPOT_APP_ID`, `HUBSPOT_DEVELOPER_API_KEY` for webhooks) | None | `{API_PUBLIC_URL}/api/connectors/oauth/hubspot/callback` | No | No | **Yes** — OAuth + 10 tools |
| Salesforce | Platform OAuth | `SALESFORCE_CLIENT_ID`, `SALESFORCE_CLIENT_SECRET` | None | `.../salesforce/callback` | **Yes** | No | **Yes** — OAuth + PKCE + 11 tools |
| QuickBooks | Platform OAuth | `QUICKBOOKS_CLIENT_ID`, `QUICKBOOKS_CLIENT_SECRET` | None | `.../quickbooks/callback` | No | No | **Yes** — OAuth + 6 tools |
| NetSuite | Platform OAuth (custom) | `NETSUITE_CLIENT_ID`, `NETSUITE_CLIENT_SECRET` | Account ID in OAuth flow | `.../netsuite/callback` | No | No | **Partial** — OAuth + 7/9 tools |
| Workday | Platform OAuth (custom) | `WORKDAY_CLIENT_ID`, `WORKDAY_CLIENT_SECRET` | Tenant URL | `.../workday/callback` | No | No | **Partial** — OAuth + 4 read tools |
| Marketo | Platform OAuth (custom) | `MARKETO_CLIENT_ID`, `MARKETO_CLIENT_SECRET` (optional; often per-org) | Munchkin ID | `.../marketo/callback` | No | No | **Partial** — OAuth + 5 tools |
| Jira | Platform OAuth | `JIRA_CLIENT_ID`, `JIRA_CLIENT_SECRET` | Atlassian cloud site | `.../jira/callback` | No | No | **Yes** — OAuth + 9 tools |
| Confluence | Platform OAuth | `JIRA_CLIENT_*` or `CONFLUENCE_CLIENT_*` | Atlassian cloud site | `.../confluence/callback` | No | No | **Partial** — OAuth only, no tools yet |
| PagerDuty | Platform OAuth | `PAGERDUTY_CLIENT_ID`, `PAGERDUTY_CLIENT_SECRET` | None | `.../pagerduty/callback` | No | No | **Yes** — OAuth + 10 tools |
| Notion | Platform OAuth | `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET` | None | `.../notion/callback` | No | No | **Partial** — OAuth only, no tools yet |
| Slack | **API key (bot token)** | None — `SLACK_SIGNING_SECRET` for slash commands only | Bot User OAuth Token (`xoxb-`) | N/A — **no OAuth route** | No | No | **Partial** — 1 tool (`slack.post_message`); not one-click OAuth |
| Google Analytics | Platform OAuth (shared Google app) | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | GA4 property selection | `.../google_analytics/callback` | No | No | **Yes** — OAuth + 2 tools |
| Google Calendar | Platform OAuth (shared) | Same as above | None | `.../google_calendar/callback` | No | No | **Yes** — OAuth + 2 tools |
| Gmail | Platform OAuth (shared) | Same as above | None | `.../gmail/callback` | No | No | **Yes** — OAuth + 3 tools |
| Google Drive | Platform OAuth (shared) | Same as above | None | `.../google_drive/callback` | No | No | **Yes** — OAuth + 2 tools |
| Google Docs | Platform OAuth (shared) | Same as above | None | `.../google_docs/callback` | No | No | **Yes** — OAuth + 1 tool |
| Google Sheets | Platform OAuth (shared) | Same as above | None | `.../google_sheets/callback` | No | No | **Yes** — OAuth + 2 tools |
| Microsoft Teams | **Not implemented** | None | N/A | N/A | No | No | **No** — catalog only; use Microsoft 365 Graph path |
| Zapier | Generic OAuth | `ZAPIER_CLIENT_ID`, `ZAPIER_CLIENT_SECRET` | None | `.../zapier/callback` | No | **Yes** | **Blocked** — partner program |
| Mailchimp | Generic OAuth | `MAILCHIMP_CLIENT_ID`, `MAILCHIMP_CLIENT_SECRET` | None | `.../mailchimp/callback` | No | No | **Partial** — OAuth route; tools catalog only |
| Constant Contact | Generic OAuth | `CONSTANT_CONTACT_CLIENT_ID`, `CONSTANT_CONTACT_CLIENT_SECRET` | None | `.../constant_contact/callback` | No | No | **Partial** — OAuth route; tools catalog only |
| Hootsuite | Generic OAuth | `HOOTSUITE_CLIENT_ID`, `HOOTSUITE_CLIENT_SECRET` | None | `.../hootsuite/callback` | No | **Yes** | **Blocked** — developer approval |
| Xero | Generic OAuth | `XERO_CLIENT_ID`, `XERO_CLIENT_SECRET` | None | `.../xero/callback` | **Yes** | No | **Partial** — OAuth + PKCE; tools catalog only |
| Airtable | Generic OAuth | `AIRTABLE_CLIENT_ID`, `AIRTABLE_CLIENT_SECRET` | None | `.../airtable/callback` | **Yes** | No | **Partial** — OAuth + PKCE; tools catalog only |
| Asana | Generic OAuth | `ASANA_CLIENT_ID`, `ASANA_CLIENT_SECRET` | None | `.../asana/callback` | No | No | **Partial** — OAuth route; tools catalog only |
| ClickUp | Generic OAuth | `CLICKUP_CLIENT_ID`, `CLICKUP_CLIENT_SECRET` | None | `.../clickup/callback` | No | No | **Partial** — OAuth route; tools catalog only |
| Freshdesk | Generic OAuth | `FRESHDESK_CLIENT_ID`, `FRESHDESK_CLIENT_SECRET` | **Subdomain** | `.../freshdesk/callback` | No | No | **Partial** — OAuth route; tools catalog only |
| Intercom | Generic OAuth | `INTERCOM_CLIENT_ID`, `INTERCOM_CLIENT_SECRET` | None | `.../intercom/callback` | No | No | **Partial** — OAuth route; tools catalog only |
| Monday.com | Generic OAuth | `MONDAY_CLIENT_ID`, `MONDAY_CLIENT_SECRET` | None | `.../monday/callback` | No | No | **Partial** — OAuth route; tools catalog only |
| Microsoft 365 | Generic OAuth | `MICROSOFT365_CLIENT_ID`, `MICROSOFT365_CLIENT_SECRET` | Tenant (admin consent) | `.../microsoft365/callback` | No | No | **Partial** — OAuth route; tools catalog only |
| Odoo | API key | None | **Odoo URL** + username + API key (Odoo Security page) | N/A | No | No | **Yes** — 12 tools via JSON-RPC API key |
| GitHub | Dual: OAuth or PAT | Optional `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | PAT **or** OAuth token | `.../github/callback` | No | No | **Yes** — 12 tools (v1–v4); OAuth or PAT |
| Zendesk | Dual: OAuth or API token | Optional `ZENDESK_CLIENT_ID`, `ZENDESK_CLIENT_SECRET` | **Subdomain** + email + API token **or** OAuth | `.../zendesk/callback` | No | No | **Yes** — 4 tools |
| Canva | Generic OAuth | `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET` | None | `.../canva/callback` | **Yes** | **Yes** | **Blocked** — Connect partner program |
| Gusto | Generic OAuth | `GUSTO_CLIENT_ID`, `GUSTO_CLIENT_SECRET` | None | `.../gusto/callback` | No | **Yes** | **Blocked** — partner approval |
| Segment | API key | None | Write key / source key | N/A | No | No | **Partial** — 3 tools |
| LinkedIn | API key | None | Marketing API token | N/A | No | No | **Partial** — 1 enrich tool |
| Stripe | API key | None | Secret key (`sk_`) | N/A | No | No | **Partial** — 2 read tools |
| Mixpanel | API key | None | Project token / service account | N/A | No | No | **No** — catalog only |
| SEMrush | API key | None | API key (BYO) | N/A | No | No | **Partial** — v1 reads (domain/keywords/backlinks) |
| Ahrefs | API key | None | API key (BYO) | N/A | No | No | **Partial** — v1 reads (DR/keywords/backlinks) |
| StackAdapt | API key | None | API token | N/A | No | No | **No** — catalog only |
| Apollo | API key | None | API key | N/A | No | No | **No** — catalog only |
| SendGrid | API key | None | API key | N/A | No | No | **No** — catalog only |
| Twilio | API key | None | Account SID + Auth Token | N/A | No | No | **No** — catalog only |
| n8n | API key | None | API key (self-hosted URL) | N/A | No | No | **No** — catalog only |
| Motion | API key | None | API key | N/A | No | No | **No** — catalog only |
| BambooHR | API key | None | API key + **subdomain** | N/A | No | No | **No** — catalog only |
| Absorb LMS | API key | None | API key + base URL | N/A | No | No | **No** — catalog only |
| Gorgias | API key | None | API key + **subdomain** | N/A | No | No | **No** — catalog only |
| Snowflake | API key / key-pair | None | Account, warehouse, DB, schema, role | N/A | No | No | **Partial** — config validation; OAuth gated off |
| ADP | API key / partner | None | Partner credentials | N/A | No | **Yes** | **Blocked** — ADP marketplace |
| PostgreSQL | Connection string | None | Connection string | N/A | No | No | **Partial** — connector create; no SQL tools |
| MongoDB | Connection string | None | Atlas connection string | N/A | No | No | **No** — catalog only |
| AWS S3 | IAM | None | Access key, secret, region, bucket | N/A | No | No | **No** — catalog only |
| Plaid | Plaid Link | `PLAID_CLIENT_ID`, `PLAID_SECRET` | `public_token` via Link UI | N/A (not OAuth callback) | No | No | **Partial** — architecture only |
| Email (SMTP) | Webhook / SMTP | None | SMTP credentials per connector | N/A | No | No | **Yes** — `email.send` tool |

---

## Section 5 — Redirect URI Master Registry

**Base:** `https://gravitre-saas-backend-production.up.railway.app`

| Vendor | Redirect URI | Shared App | PKCE Required | Sandbox URI |
|--------|--------------|------------|---------------|-------------|
| HubSpot | `/api/connectors/oauth/hubspot/callback` | Dedicated | No | Same app or `HUBSPOT_SANDBOX_*` env |
| Salesforce | `/api/connectors/oauth/salesforce/callback` | Dedicated | No | `SALESFORCE_SANDBOX_*` Connected App |
| QuickBooks | `/api/connectors/oauth/quickbooks/callback` | Dedicated | No | Intuit sandbox app |
| NetSuite | `/api/connectors/oauth/netsuite/callback` | Dedicated | No | NetSuite sandbox account |
| Workday | `/api/connectors/oauth/workday/callback` | Dedicated | No | Workday sandbox tenant |
| Marketo | `/api/connectors/oauth/marketo/callback` | Dedicated | No | Marketo sandbox |
| Jira | `/api/connectors/oauth/jira/callback` | Atlassian app (shared with Confluence) | No | Atlassian dev site |
| Confluence | `/api/connectors/oauth/confluence/callback` | Atlassian app | No | Atlassian dev site |
| PagerDuty | `/api/connectors/oauth/pagerduty/callback` | Dedicated | No | PagerDuty sandbox |
| Notion | `/api/connectors/oauth/notion/callback` | Dedicated | No | Notion integration |
| Google Analytics | `/api/connectors/oauth/google_analytics/callback` | **Shared Google Cloud OAuth** | No | Same Google project |
| Google Calendar | `/api/connectors/oauth/google_calendar/callback` | Shared | No | Same |
| Gmail | `/api/connectors/oauth/gmail/callback` | Shared | No | Same |
| Google Drive | `/api/connectors/oauth/google_drive/callback` | Shared | No | Same |
| Google Docs | `/api/connectors/oauth/google_docs/callback` | Shared | No | Same |
| Google Sheets | `/api/connectors/oauth/google_sheets/callback` | Shared | No | Same |
| Mailchimp | `/api/connectors/oauth/mailchimp/callback` | Dedicated | No | Mailchimp dev |
| Constant Contact | `/api/connectors/oauth/constant_contact/callback` | Dedicated | No | CC sandbox |
| Xero | `/api/connectors/oauth/xero/callback` | Dedicated | **Yes** | Xero demo company |
| Airtable | `/api/connectors/oauth/airtable/callback` | Dedicated | **Yes** | Airtable dev |
| Asana | `/api/connectors/oauth/asana/callback` | Dedicated | No | Asana dev workspace |
| ClickUp | `/api/connectors/oauth/clickup/callback` | Dedicated | No | ClickUp dev |
| Freshdesk | `/api/connectors/oauth/freshdesk/callback` | Dedicated | No | Freshdesk sandbox |
| Intercom | `/api/connectors/oauth/intercom/callback` | Dedicated | No | Intercom dev |
| Monday.com | `/api/connectors/oauth/monday/callback` | Dedicated | No | Monday dev |
| Microsoft 365 | `/api/connectors/oauth/microsoft365/callback` | Entra app | No | Microsoft dev tenant |
| Odoo | N/A (API key per connector) | Customer Odoo URL | No | Odoo SaaS or self-hosted |
| GitHub | `/api/connectors/oauth/github/callback` | Dedicated OAuth App | No | Same |
| Zendesk | `/api/connectors/oauth/zendesk/callback` | Per-subdomain OAuth client | No | Zendesk sandbox |
| Canva | `/api/connectors/oauth/canva/callback` | Dedicated | **Yes** | Canva dev |
| Gusto | `/api/connectors/oauth/gusto/callback` | Dedicated | No | Gusto demo |
| Hootsuite | `/api/connectors/oauth/hootsuite/callback` | Dedicated | No | Hootsuite dev |
| Zapier | `/api/connectors/oauth/zapier/callback` | Dedicated | No | Zapier partner |

**Google shared architecture:** One Google Cloud project → one OAuth 2.0 Client ID → six product-specific callback URLs registered on the same client. Env: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`. See `docs/integration/GOOGLE_OAUTH.md`.

---

## Section 6 — Scopes Matrix (summary)

Full per-vendor scopes are in `GET /api/connectors/catalog/actions` and `backend/app/connectors/action_catalog/`. Below: **minimum OAuth consent scopes** to register at the vendor portal (may be broader than tool scopes).

| Vendor | v1 Read (minimum) | v2 Write (minimum) | v3 Advanced | Dangerous / Admin |
|--------|-------------------|--------------------|--------------|-------------------|
| HubSpot | `crm.objects.contacts.read`, `crm.objects.deals.read` | `crm.objects.contacts.write`, `crm.objects.deals.write` | `automation`, `crm.lists.write` | `crm.schemas.*`, full account |
| Salesforce | `api` + object read perms via Connected App | Create/update on Lead, Account, Opportunity | Bulk API, admin | `full`, `refresh_token` always |
| QuickBooks | `com.intuit.quickbooks.accounting` (read) | Accounting write scope | Payments, payroll (separate products) | Company admin |
| Google (all) | Product-specific read scopes (e.g. `calendar.readonly`, `gmail.readonly`) | Product write scopes | `drive`, `spreadsheets` batch | `admin.directory.*` |
| Jira/Confluence | `read:jira-work`, `read:confluence-content.all` | `write:jira-work`, `write:confluence-content` | Webhooks, admin | `manage:jira-project` |
| PagerDuty | `read` incidents, services | `write` incidents | Escalation policies | Account admin |
| Notion | `read` content | `update` content | Insert, databases | Workspace admin |
| Microsoft 365 | `User.Read`, `Mail.Read`, `Calendars.Read`, `Files.Read.All` | `Mail.Send`, `Calendars.ReadWrite` | `Sites.ReadWrite.All` | `Directory.ReadWrite.All` |
| GitHub (OAuth) | `repo` (private), `read:user` | Issues, PRs | `workflow` dispatch | `admin:org`, `delete_repo` |
| Zendesk (OAuth) | `read` | `write` | Macros, merge | Admin API |
| Xero | `accounting.transactions`, `accounting.contacts`, `offline_access` | Write scopes on accounting | Payroll, files | Organisation settings |
| Airtable | `data.records:read`, `schema.bases:read` | `data.records:write` | Webhooks | Base admin |
| Segment | N/A (API key) | `identify`, `track` | `group`, batch | Workspace admin token |
| Stripe | N/A (restricted key) | Read-only key for v1 | Write key for refunds | Secret key full access |

---

## Section 10 — Executive Dashboard

| Vendor | Auth Ready | UI Ready | Tool Ready | Production Ready | Revenue Impact |
|--------|------------|----------|------------|------------------|----------------|
| HubSpot | Yes | Yes | Yes (10) | **Yes** | High |
| Salesforce | Yes | Yes | Yes (11) | **Yes** | High |
| Slack | **No OAuth** | Yes | Partial (1) | Partial | High |
| Google Workspace (6) | Yes | Yes | Yes (12 total) | **Yes** | High |
| Jira | Yes | Yes | Yes (9) | **Yes** | High |
| PagerDuty | Yes | Yes | Yes (10) | **Yes** | Medium |
| QuickBooks | Yes | Yes | Partial (6) | **Yes** | High |
| Zendesk | Yes | Yes | Yes (4) | **Yes** | High |
| GitHub | Partial | Yes | Yes (4) | **Yes** | High |
| Notion | Yes | Yes | No | Partial | High |
| Confluence | Yes | Yes | No | Partial | Medium |
| NetSuite | Yes | Yes | Partial | Partial | High |
| Workday | Yes | Yes | Partial | Partial | Medium |
| Marketo | Yes | Yes | Partial | Partial | Medium |
| Segment | Yes | Yes | Partial (3) | Partial | Medium |
| Stripe | Yes | Yes | Partial (2) | Partial | High |
| LinkedIn | Yes | Yes | Partial (1) | Partial | Medium |
| Generic OAuth (17) | Routes yes | oauthReady | Catalog only | Partial | Varies |
| API key (16) | Yes | Yes | Mostly catalog | No | Varies |
| PostgreSQL | Yes | Yes | No SQL tools | Partial | Medium |
| Plaid | Partial | Partial | No | No | Medium |
| Partner-gated (6) | Routes/catalog | Flagged | No | **Blocked** | Medium |

### Totals

| Metric | Count |
|--------|------:|
| Total connectors in catalog | 57 |
| OAuth callback routes implemented | 33 |
| API key connectors | 16 |
| Database connectors | 2 |
| IAM connectors | 1 |
| Partner-gated | 6 |
| **Production-ready** (OAuth + meaningful tools) | **~15** |
| Connectors needing engineering work | **~42** |
| Registered `invoke_tool` actions | 100 |

---

## References

- `docs/CONNECTOR_AUTH_PRODUCTION_READINESS.md`
- `docs/CONNECTOR_CREDENTIAL_ACQUISITION_PLAYBOOK.md`
- `docs/CONNECTOR_PRODUCTION_READINESS_REPORT.md`
- `docs/CONNECTOR_ROADMAP.md`
- `backend/.env.example`
- `docs/integration/HUBSPOT_PLATFORM_SETUP.md`

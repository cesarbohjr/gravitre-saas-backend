# Gravitre Connector Production Readiness Report

**Audit date:** May 29, 2026  
**Auditor role:** Principal Integration Architect (codebase-derived)  
**Scope:** All 57 catalog connectors + OAuth security + tool execution layer

---

## Executive summary

Gravitre has a **production-grade OAuth foundation** for ~33 vendors with working callback routes, PKCE for Airtable/Canva/Xero, signed state with replay protection, and encrypted token storage. **~15 connectors** are production-ready for customer use (OAuth or API key + real `invoke_tool` handlers). The remaining catalog entries have **credential UI + action catalog + demo workflows** but need either platform OAuth apps, partner approval, or engineering to implement API clients.

**Critical gap:** Slack is marketed as OAuth in the catalog but uses **bot tokens only** — not HubSpot-style one-click OAuth.

---

## Section 4 — Production Readiness Audit

### OAuth providers (33 routes)

| Check | Status | Notes |
|-------|--------|-------|
| Authorization code flow | **Pass** | Tier 1–3 dedicated + generic registry |
| Callback URL consistency | **Pass** | `{API_PUBLIC_URL}/api/connectors/oauth/{vendor}/callback` |
| Signed OAuth state (jti, nonce) | **Pass** | `oauth_state.py`, replay protection |
| PKCE (Airtable, Canva, Xero) | **Pass** | RFC 7636 S256 in `oauth_pkce.py` |
| Token encryption at rest | **Pass** | `CONNECTOR_SECRETS_ENCRYPTION_KEY` |
| Token refresh | **Pass** | Per-vendor `ensure_*_access_token` patterns |
| Partner-gated flagged | **Pass** | Catalog `requiresPartnerApproval` |
| Microsoft admin consent | **Risk** | Multitenant Entra apps may need admin approval |
| Odoo self-hosted variance | **Risk** | Instance URL + OAuth vs API key |
| Slack OAuth route | **Fail** | No `/api/connectors/oauth/slack` — bot token only |

### PKCE providers

| Vendor | Portal PKCE | Gravitre PKCE | E2E tested |
|--------|-------------|---------------|------------|
| Airtable | Required | Implemented | Needs platform app |
| Canva | Required | Implemented | Partner blocked |
| Xero | Required | Implemented | Needs platform app |

### API key providers (16)

| Check | Status |
|-------|--------|
| Encrypted per-connector storage | **Pass** |
| No fake platform OAuth env vars | **Pass** (Claude/SendGrid/Twilio removed) |
| Tool implementations | **Partial** — Segment, Stripe, LinkedIn only |
| Scope registration in catalog | **Pass** |

### Database providers

| Vendor | Connector create | SQL/document tools | Production |
|--------|------------------|--------------------|------------|
| PostgreSQL | **Pass** | **Fail** | Partial |
| MongoDB | **Pass** | **Fail** | No |

### IAM providers

| Vendor | Credential collection | S3 tools | Production |
|--------|----------------------|----------|------------|
| AWS S3 | **Pass** | **Fail** | No |

### Partner-gated providers

| Vendor | Catalog flag | OAuth route | Blocker |
|--------|--------------|-------------|---------|
| Zapier | Yes | Yes | Partner program |
| Hootsuite | Yes | Yes | Developer approval |
| Gusto | Yes | Yes | Partner approval |
| Canva | Yes | Yes | Connect partner + PKCE |
| ADP | Yes | N/A | Marketplace partner |
| Plaid | N/A | N/A | Link UI incomplete |

---

## Issue register

### Critical

| ID | Issue | Vendors | Remediation |
|----|-------|---------|-------------|
| C-01 | Slack catalog says OAuth but no OAuth route | Slack | Implement `slack_oauth.py` + `SLACK_CLIENT_ID/SECRET` or change catalog to API key |
| C-02 | `API_PUBLIC_URL` / redirect mismatch in production | All OAuth | Audit Railway env vs registered URIs at each vendor |
| C-03 | Partner connectors shown as connectable | Zapier, Canva, Gusto, Hootsuite, ADP | Sales gating + UI "Request access" |

### High

| ID | Issue | Vendors | Remediation |
|----|-------|---------|-------------|
| H-01 | OAuth without tools | Notion, Confluence, 17 generic OAuth | Implement v1 read tools per roadmap |
| H-02 | Plaid Link not end-to-end | Plaid | Frontend Link + `public_token` exchange endpoint |
| H-03 | Microsoft 365 admin consent | Microsoft 365, Teams | Document tenant admin flow; consider single-tenant option |
| H-04 | Snowflake OAuth disabled | Snowflake | Keep password/key-pair only until OAuth certified |

### Medium

| ID | Issue | Vendors | Remediation |
|----|-------|---------|-------------|
| M-01 | Partial tool coverage | NetSuite, QuickBooks, Marketo, Workday | Complete v2/v3 catalog actions |
| M-02 | GitHub OAuth optional; PAT default | GitHub | Document both paths in Connectors UI |
| M-03 | Zendesk dual auth complexity | Zendesk | OAuth Bearer vs email+token UX |
| M-04 | Freshdesk/Odoo subdomain/instance | Freshdesk, Odoo, Zendesk | Validate at connect time |

### Low

| ID | Issue | Vendors | Remediation |
|----|-------|---------|-------------|
| L-01 | Catalog actions not implemented | ~40 vendors | Phased tool implementation |
| L-02 | Demo workflows reference unimplemented tools | All | Gate workflow templates on `implemented: true` |
| L-03 | Microsoft Teams separate from M365 | Teams | Merge into M365 Graph or build Teams module |

---

## Section 7 — OAuth connector classification

### Category A — Ready now (add platform credentials → one-click works)

HubSpot, Salesforce, QuickBooks, Jira, PagerDuty, Google (6 products), Zendesk (API token path), GitHub (PAT path), Gmail, Google Calendar, Google Analytics, Google Drive, Google Docs, Google Sheets

**Missing work:** Platform env vars in Railway only.  
**Effort:** 1–2 days operator time per vendor app registration.

### Category B — One sprint away

NetSuite, Workday, Marketo, Notion, Confluence, Mailchimp, Asana, Monday, Intercom, Xero, Airtable, Stripe (tools), Segment (expand), LinkedIn (expand), Email/SMTP

**Missing work:** Platform OAuth apps + tool implementations for Notion/Confluence/generic OAuth.  
**Effort:** 1–2 engineering sprints per cluster.

### Category C — Partner approval blocked

Zapier, Hootsuite, Gusto, Canva, ADP

**Missing work:** Business development + vendor partner onboarding.  
**Effort:** Weeks to months (not engineering-only).

### Category D — Cannot become true one-click (as designed)

| Vendor | Reason |
|--------|--------|
| Segment, SendGrid, Twilio, Mixpanel, etc. | API-key-only by vendor design — no customer OAuth |
| PostgreSQL, MongoDB | Connection string — no OAuth |
| AWS S3 | IAM keys — no OAuth |
| Plaid | Plaid Link — not authorization-code OAuth |
| Anthropic/OpenAI | Platform AI keys — not connectors |
| Snowflake (today) | OAuth intentionally gated; password/key-pair only |

**Slack** should move from D to A after OAuth implementation.

---

## HubSpot gold standard — technical deep dive

```
Customer clicks Connect
    → POST /api/connectors/oauth/hubspot/start
    → prepare_oauth_connector() creates pending connector row
    → Redirect to HubSpot authorize URL with signed state (jti, nonce, org_id, user_id)
    → Customer grants consent
    → GET /api/connectors/oauth/hubspot/callback?code=...&state=...
    → verify_oauth_state() — replay check, provider binding
    → Exchange code for access + refresh tokens
    → store_oauth_tokens() encrypted in connector_secrets
    → mark_connector_oauth_success() → status active
    → Agent/workflow invokes hubspot.contacts.get
    → ensure_hubspot_access_token() refreshes if needed
    → HubSpot CRM API v3 call
    → NormalizedResult → audit log
```

**Multi-tenant:** One HubSpot **platform app** serves all Gravitre customers; each org gets isolated encrypted tokens keyed by `connector_id` + `org_id`.

**Secret handling:** Client secret never leaves Railway; customers never see it. Refresh tokens rotated per HubSpot policy.

---

## Verification checklist (production launch)

- [ ] `CONNECTOR_SECRETS_ENCRYPTION_KEY` set and stable in Railway production
- [ ] `API_PUBLIC_URL` = `https://gravitre-saas-backend-production.up.railway.app`
- [ ] Every Category A vendor: redirect URI registered at vendor portal
- [ ] HubSpot + Salesforce smoke: connect → tool invoke → audit event
- [ ] PKCE vendors tested with real platform apps
- [ ] Partner-gated vendors hidden or labeled in Connectors UI
- [ ] No `CLAUDE_CLIENT_*` or fake OAuth env vars deployed
- [ ] Plaid not exposed as OAuth connect button

---

## References

- `docs/CONNECTOR_IMPLEMENTATION_MATRIX.md`
- `docs/CONNECTOR_CREDENTIAL_ACQUISITION_PLAYBOOK.md`
- `docs/CONNECTOR_AUTH_PRODUCTION_READINESS.md`
- `backend/app/connectors/oauth_pkce.py`
- `backend/app/routers/connector_oauth.py`
- `backend/tests/connectors/` (OAuth + PKCE tests)

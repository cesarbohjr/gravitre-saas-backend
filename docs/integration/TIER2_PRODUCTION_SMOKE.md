# Tier 2 production smoke checklist

Run after Tier 1 connector platform is verified (`TIER1_PRODUCTION_SMOKE.md`) and backend is deployed.

**API:** `https://gravitre-saas-backend-production.up.railway.app`  
**App:** `https://gravitre.app`

Tier 2 code is implemented; this checklist verifies **production wiring** per epic.

---

## Prerequisites

- `CONNECTOR_SECRETS_ENCRYPTION_KEY` on Railway
- `API_PUBLIC_URL` / `PUBLIC_APP_URL` set
- Per-vendor OAuth env vars (see `backend/.env.example`)

---

## Epic A — Salesforce (STA-30–32)

| Step | Action | Pass |
|------|--------|------|
| A.1 | `GET .../oauth/salesforce/status` → configured | ☐ |
| A.2 | Connectors → Salesforce → Complete OAuth | ☐ |
| A.3 | Test connection succeeds | ☐ |
| A.4 | Agent tool: `salesforce.leads.get` (optional) | ☐ |

---

## Epic B — Finance (STA-33–35)

| Step | Action | Pass |
|------|--------|------|
| B.1 | QuickBooks OAuth status → configured | ☐ |
| B.2 | Connect QuickBooks → OAuth completes | ☐ |
| B.3 | Stripe: Add connector with secret API key → Save | ☐ |
| B.4 | Agent tool: `quickbooks.invoices.list` or `stripe.invoices.list` | ☐ |

---

## Epic C — DevOps (STA-36–39)

| Step | Action | Pass |
|------|--------|------|
| C.1 | Jira OAuth connect + test | ☐ |
| C.2 | Confluence OAuth connect + test | ☐ |
| C.3 | PagerDuty OAuth connect + test | ☐ |
| C.4 | DevOps workflow template seeds (PagerDuty → Jira → Slack) | ☐ |

---

## Epic D — Marketing Analytics (STA-40–42)

| Step | Action | Pass |
|------|--------|------|
| D.1 | Google Analytics OAuth connect | ☐ |
| D.2 | GA4 property picker after OAuth (if multi-property) | ☐ |
| D.3 | `google_analytics.reports.run` tool call | ☐ |

---

## Epic E — Knowledge sync (STA-43–46)

| Step | Action | Pass |
|------|--------|------|
| E.1 | Notion OAuth connect | ☐ |
| E.2 | Confluence OAuth connect (RAG sync) | ☐ |
| E.3 | Manual sync on connector → job completes | ☐ |

---

## Epic F — Platform (STA-47–49)

| Step | Action | Pass |
|------|--------|------|
| F.1 | Workflow schedule fires (cron worker) | ☐ |
| F.2 | Council debate → workflow branch | ☐ |
| F.3 | Agent memories API (replace mock UI data) | ☐ |

---

## Tier 2 “done” definition

- All OAuth rows in sections **A–E** pass connect + test in production.
- API key connectors (Stripe) save and test.
- Linear STA-24–29 epics marked **Done** after verification.

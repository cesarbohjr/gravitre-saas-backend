# Tier 1 production smoke checklist

Use after HubSpot/Salesforce env vars are on Railway and the **latest backend** is deployed to `gravitre-saas-backend`.

**API base:** `https://gravitre-saas-backend-production.up.railway.app`  
**App:** `https://gravitre.app`

---

## 0. Operator env (one-time)

```powershell
# Copy credentials from HubSpot → Project → Gravitre Operator → Auth
$env:HUBSPOT_CLIENT_ID="<client-id>"
$env:HUBSPOT_CLIENT_SECRET="<client-secret>"
.\scripts\fill-hubspot-operator-env.ps1

# Or if already in backend/.env.hubspot.local:
.\scripts\fill-hubspot-operator-env.ps1
```

Salesforce vars are already in `backend/.env.operator.local` and were pushed via `npm run hubspot:railway`.

`CONNECTOR_SECRETS_ENCRYPTION_KEY` on Railway is **not** overwritten if already set (legacy Fernet is OK).

---

## 1. Deploy backend

Push `main` (or your release branch) so Railway redeploys **gravitre-saas-backend**.

Confirm new routes exist (should **not** be 404):

```powershell
npm run hubspot:check
curl.exe -s "https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/salesforce/status"
```

Expected: JSON with `configured` / `encryptionConfigured` (not `{"detail":"Not Found"}`).

---

## 2. HubSpot OAuth (STA-14 / STA-125)

| Step | Action | Pass |
|------|--------|------|
| 2.1 | `npm run hubspot:check` → `configured: true`, `encryptionConfigured: true` | ☐ |
| 2.2 | Log in to Gravitre → **Connectors** → **Connect HubSpot** | ☐ |
| 2.3 | Complete HubSpot consent; land on `/connectors?oauth=success` | ☐ |
| 2.4 | Connector row shows **healthy**; **Test connection** succeeds | ☐ |

---

## 3. Salesforce OAuth (STA-30, Tier 2 code on Tier 1 platform)

| Step | Action | Pass |
|------|--------|------|
| 3.1 | `GET .../api/connectors/oauth/salesforce/status` → configured | ☐ |
| 3.2 | **Connectors** → **Connect Salesforce** → OAuth completes | ☐ |
| 3.3 | Test connection succeeds | ☐ |

---

## 4. Tool connectors (STA-21–23)

| Connector | Setup | Pass |
|-----------|--------|------|
| Zendesk | Subdomain + email + API token in UI | ☐ |
| GitHub | Owner + repo + PAT | ☐ |
| Google Calendar | Access token (stretch) | ☐ |

Run one agent/tool call per connector if you use them in workflows.

---

## 5. HubSpot tools & triggers (STA-15–16)

| Step | Action | Pass |
|------|--------|------|
| 5.1 | Agent/workflow invokes a HubSpot tool (e.g. list contacts) | ☐ |
| 5.2 | Optional: inbound webhook test (`docs/integration/HUBSPOT_TRIGGERS.md`) | ☐ |

Requires `HUBSPOT_APP_ID` (+ developer key for programmatic subscription sync) only for STA-16 automations.

---

## 6. Tier 1 demo milestone (STA-15 + STA-18)

| Step | Action | Pass |
|------|--------|------|
| 6.1 | Seed org has demo workflow (`org_seed_service.py` lines 89–100) | ☐ |
| 6.2 | Run workflow with HubSpot connected + `next_agent_id` routing | ☐ |
| 6.3 | Handoff payload visible on downstream agent step | ☐ |

---

## 7. Regression

```powershell
$env:BACKEND_URL="https://gravitre-saas-backend-production.up.railway.app"
.\scripts\test-integration.ps1
```

| Check | Pass |
|-------|------|
| `/health` → `status: ok` | ☐ |
| Unauthenticated `/api/assistant/chat` → **401** | ☐ |

---

## Tier 1 “done” definition

- All rows in sections **1–5** pass in **production**.
- Section **6** passes if you use the demo workflow as the release gate.
- Linear issues STA-10–23 (+ STA-125 ops) marked **Done** in Linear after verification.

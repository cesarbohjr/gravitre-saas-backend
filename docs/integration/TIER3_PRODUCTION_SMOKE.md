# Tier 3 production smoke checklist

Run after Tier 2 verification (`TIER2_PRODUCTION_SMOKE.md`).

**API:** `https://gravitre-saas-backend-production.up.railway.app`  
**App:** `https://gravitre.app`

---

## Prerequisites

- Tier 1 platform complete (STA-10, STA-11, STA-13)
- `CONNECTOR_SECRETS_ENCRYPTION_KEY` on Railway
- Operator env scripts: `npm run netsuite:fill-env`, `workday:fill-env`, `marketo:fill-env`

---

## Epic A — NetSuite (STA-56–58)

| Step | Action | Pass |
|------|--------|------|
| A.1 | `npm run netsuite:check` → READY | ☐ |
| A.2 | Connect NetSuite with account ID | ☐ |
| A.3 | Agent tool: `netsuite.customers.get` | ☐ |

## Epic B — Workday (STA-59–61)

| Step | Action | Pass |
|------|--------|------|
| B.1 | `npm run workday:check` → READY | ☐ |
| B.2 | Connect Workday with tenant URL + tenant name | ☐ |
| B.3 | Agent tool: `workday.workers.list` | ☐ |
| B.4 | Workday → RAG sync admin endpoint | ☐ |

## Epic C — LinkedIn (STA-62–63)

| Step | Action | Pass |
|------|--------|------|
| C.1 | Add LinkedIn connector with Marketing API token | ☐ |
| C.2 | Agent tool: `linkedin.prospect.enrich` | ☐ |

## Epic D — Marketo (STA-64–66)

| Step | Action | Pass |
|------|--------|------|
| D.1 | `npm run marketo:check` → READY | ☐ |
| D.2 | Connect Marketo with Munchkin ID | ☐ |
| D.3 | Agent tool: `marketo.leads.get` | ☐ |

## Epic E — Segment (STA-67–69)

| Step | Action | Pass |
|------|--------|------|
| E.1 | Add Segment connector with write key | ☐ |
| E.2 | Agent tool: `segment.identify` / `segment.track` | ☐ |
| E.3 | Segment inbound webhook → workflow trigger | ☐ |

## Epic F — Marketplace (STA-70–73)

| Step | Action | Pass |
|------|--------|------|
| F.1 | Partner submission at `/marketplace/submit` | ☐ |
| F.2 | Sandbox org at `/marketplace/sandbox` | ☐ |
| F.3 | Demo invoke `POST /api/marketplace/sandbox/demo` | ☐ |

---

## Quick operator checks

```powershell
npm run netsuite:check
npm run workday:check
npm run marketo:check
npm run oauth:check-all
```

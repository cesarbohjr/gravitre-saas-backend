# Tier 4 production smoke checklist

Run after Tier 3 marketplace foundation (STA-70–73).

**API:** `https://gravitre-saas-backend-production.up.railway.app`  
**App:** `https://gravitre.app`

---

## Epic A — Security & Compliance (STA-80–83)

| Step | Action | Pass |
|------|--------|------|
| A.1 | `GET /api/enterprise/data-region` returns org region | ☐ |
| A.2 | `PUT /api/enterprise/data-region` sets `us` or `eu` | ☐ |
| A.3 | `GET /api/enterprise/compliance/soc2-export` returns redacted bundle | ☐ |
| A.4 | Configure SIEM at `PUT /api/enterprise/siem` + test delivery | ☐ |

## Epic B — Deploy & Identity (STA-84–86)

| Step | Action | Pass |
|------|--------|------|
| B.1 | `GET/PUT /api/enterprise/branding` updates logo/color | ☐ |
| B.2 | SAML SSO connect flow via `/api/sso` | ☐ |
| B.3 | SCIM token provision + user sync `/scim/v2/Users` | ☐ |
| B.4 | Review `deploy/enterprise/` Helm chart | ☐ |

## Epic C — HR & Finance (STA-87–89)

| Step | Action | Pass |
|------|--------|------|
| C.1 | BambooHR connector + `bamboohr.employees.list` | ☐ |
| C.2 | Greenhouse connector + `greenhouse.jobs.list` | ☐ |
| C.3 | Xero OAuth + `xero.invoices.list` | ☐ |

## Epic D — AI Governance & Analytics (STA-90–92)

| Step | Action | Pass |
|------|--------|------|
| D.1 | Model policy `GET/PUT /api/settings/model-policy` | ☐ |
| D.2 | Workforce analytics `GET /api/enterprise/workforce-analytics` | ☐ |
| D.3 | Cost attribution `GET /api/enterprise/cost-attribution` | ☐ |

## Epic E — Scale & Reliability (STA-93–95)

| Step | Action | Pass |
|------|--------|------|
| E.1 | `GET /api/enterprise/execution-region` shows region + queue | ☐ |
| E.2 | Redis-backed workflow queue configured (`REDIS_URL`) | ☐ |
| E.3 | DR runbook reviewed (`docs/integration/workflow-dr-runbook.md`) | ☐ |

## Epic F — Marketplace Scale (STA-96–99)

| Step | Action | Pass |
|------|--------|------|
| F.1 | Marketplace billing `/marketplace/billing` | ☐ |
| F.2 | Partner certification scan on submit | ☐ |
| F.3 | Private connector upload `/marketplace/private` | ☐ |
| F.4 | Fine-tuned model assignment on agent | ☐ |

# Tier 5 production smoke checklist

Run after Tier 5 compliance + vertical packs (STA-106–115).

**API:** `https://gravitre-saas-backend-production.up.railway.app`  
**App:** `https://gravitre.app`

---

## Automated smoke (vertical packs)

Requires `backend/.env` or `backend/.env.operator.local` with `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_JWT_SECRET`.

```bash
npm run clio:check      # Clio OAuth configured on API host
npm run smoke:tier5     # legal install → workflow execute → real-estate install
```

Optional: set `BACKEND_URL` to target a non-production host.

---

## Epic A — Autonomous execution (STA-106–109)

| Step | Action | Pass |
|------|--------|------|
| A.1 | Enable auto-execute on an operator; policy gate blocks unsafe runs | ☐ |
| A.2 | `POST /api/runs/{id}/interrupt` pauses in-flight autonomous run | ☐ |
| A.3 | Daily autonomous budgets block over-limit runs | ☐ |
| A.4 | Failed run triggers compensating transaction where supported | ☐ |

## Epic B — Regulated compliance (STA-110–112)

| Step | Action | Pass |
|------|--------|------|
| B.1 | HIPAA PHI controls on healthcare connector/tools | ☐ |
| B.2 | FedRAMP gap assessment export | ☐ |
| B.3 | EU AI Act transparency log export | ☐ |

## Epic C — Industry vertical packs (STA-113–115)

| Step | Action | Pass |
|------|--------|------|
| C.1 | `POST /api/verticals/healthcare/install` seeds FHIR sandbox + prior-auth workflow | ☐ |
| C.2 | `POST /api/verticals/legal/install` seeds Clio demo + intake workflow | ☐ |
| C.3 | `npm run clio:check` → `configured: true` | ☐ |
| C.4 | `POST /api/workflows/execute` with legal `intakeWorkflowId` queues run | ☐ |
| C.5 | `POST /api/verticals/real-estate/install` seeds listing workflow + agents | ☐ |
| C.6 | Connect Clio OAuth at `/connectors` (redirect URI on Clio developer app) | ☐ |

**Docs:** `docs/integration/legal-vertical-pack.md`, `docs/integration/real-estate-vertical-pack.md`

---

## Operator env scripts

| Vertical | Railway env | Check |
|----------|-------------|-------|
| Legal (Clio) | `npm run clio:fill-env` | `npm run clio:check` |

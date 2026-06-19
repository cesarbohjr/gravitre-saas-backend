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
| A.1 | Enable auto-execute on an operator; policy gate blocks unsafe runs | ☑ |
| A.2 | `POST /api/runs/{id}/interrupt` pauses in-flight autonomous run | ☑ |
| A.3 | Daily autonomous budgets block over-limit runs | ☑ |
| A.4 | Failed run triggers compensating transaction where supported | ☑ |

## Epic B — Regulated compliance (STA-110–112)

| Step | Action | Pass |
|------|--------|------|
| B.1 | HIPAA PHI controls on healthcare connector/tools | ☑ |
| B.2 | FedRAMP gap assessment export | ☑ |
| B.3 | EU AI Act transparency log export | ☑ |

## Epic C — Industry vertical packs (STA-113–115)

| Step | Action | Pass |
|------|--------|------|
| C.1 | `POST /api/verticals/healthcare/install` seeds FHIR sandbox + prior-auth workflow | ☐ |
| C.2 | `POST /api/verticals/legal/install` seeds Clio demo + intake workflow | ☐ |
| C.3 | `npm run clio:check` → `configured: true` | ☐ |
| C.4 | `POST /api/workflows/execute` with legal `intakeWorkflowId` queues run | ☐ |
| C.5 | `POST /api/verticals/real-estate/install` seeds listing workflow + agents | ☐ |
| C.6 | Connect Clio OAuth at `/connectors` (redirect URI on Clio developer app) | ⚠ OAuth start OK; finish in browser |

**Docs:** `docs/integration/legal-vertical-pack.md`, `docs/integration/real-estate-vertical-pack.md`

---

## Epic D — Multi-org federation (STA-116–118)

| Step | Action | Pass |
|------|--------|------|
| D.1 | `POST /api/federation/partnerships` creates B2B partnership | ☑ |
| D.2 | Federated connector consent flow completes | ☑ |
| D.3 | `POST /api/federation/delegated-tasks` queues cross-org task | ☑ |

**Docs:** `docs/integration/b2b-handoff-protocol.md`, `docs/integration/delegated-external-tasks.md`

## Epic E — Advanced AI workforce (STA-119–121)

| Step | Action | Pass |
|------|--------|------|
| E.1 | `POST /api/agent-swarm` coordinates multi-agent run | ☑ |
| E.2 | `POST /api/workflows/digital-twin` simulates without side effects | ☑ |
| E.3 | `GET /api/marketplace/role-packs` lists department packs | ☑ |
| E.4 | `POST /api/marketplace/role-packs/sales-ops/install` (admin) | ☑ |
| E.5 | `/marketplace/role-packs` UI install flow | ☑ |

**Docs:** `docs/integration/multi-agent-swarm-coordinator.md`, `docs/integration/workflow-digital-twin.md`, `docs/integration/agent-role-marketplace.md`

## Epic F — Platform intelligence (STA-122–124)

| Step | Action | Pass |
|------|--------|------|
| F.1 | `POST /api/workflows/{id}/failure-predictions/scan` persists alerts | ☑ |
| F.2 | `POST /api/enterprise/integration-suggestions/scan` persists suggestions | ☑ |
| F.3 | `GET /api/enterprise/integration-health` returns composite score | ☑ |
| F.4 | `POST /api/enterprise/integration-health/snapshot` records trend point | ☑ |
| F.5 | `/settings/enterprise?tab=cs` CS dashboard loads all panels | ☑ |

**Docs:** `docs/integration/predictive-workflow-failure.md`, `docs/integration/auto-suggest-connectors-workflows.md`, `docs/integration/integration-health-score.md`

---

## Manual epic smoke (Epics A–F API + app routes)

Runs policy gates, compliance exports, federation, swarm, role packs, and CS dashboard APIs against production.

```bash
npm run smoke:tier5-manual   # writes docs/delivery/smoke-tier5-manual-latest.json
```

**Note:** C.6 (Clio OAuth connect) requires completing the browser OAuth flow at [https://gravitre.app/connectors](https://gravitre.app/connectors) after `POST /api/connectors/oauth/clio/start` returns an authorization URL.

---

## Marketplace production smoke (STA-229 / STA-239)

Requires the same Supabase secrets as other prod smokes (`backend/.env.operator.local` locally; GitHub Actions secrets in CI).

```bash
npm run smoke:marketplace-production
npm run smoke:marketplace-production:report   # writes docs/delivery/smoke-marketplace-production-latest.json
```

Asserts unified catalog `total ≥ 50` (STA-229), browse/detail/entitlement/install-check, analytics, billing, and publisher routes.

**CI:** `.github/workflows/marketplace-production-smoke.yml` (nightly 04:30 UTC) and Lane D `.github/workflows/production-hardening-smoke.yml` (05:00 UTC). Secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`.

---

## Lane D — Production hardening (nightly)

Automated read-only verification against Railway production:

| Workflow | Schedule | Scripts |
|----------|----------|---------|
| `marketplace-production-smoke.yml` | 04:30 UTC | `smoke-marketplace-production.py` |
| `production-hardening-smoke.yml` | 05:00 UTC | seed catalog test + `smoke-post-tier5` + marketplace + `smoke-ai-production` |

Manual:

```bash
npm run smoke:post-tier5
npm run smoke:marketplace-production:report
npm run smoke:ai-production:report
```

---

## Post–Tier 5 automated smoke

```bash
npm run smoke:post-tier5   # STA-121–124 APIs + role packs catalog
```

See `docs/integration/POST_TIER5_BACKLOG.md` for UI and Tier 6 planning.

---

## AI production smoke (STA-173 / IMPL 8)

Run after Epic I wiring (Meson, agent chat, assign task, workflow run/preview, CS dashboard, role packs, federation, run interrupt).

```bash
npm run smoke:ai-production
npm run smoke:ai-production:report   # writes docs/delivery/smoke-ai-production-latest.json
```

Covers: `/health`, Meson interpret, agents list, agent job enqueue (+ poll), assistant chat (SSE), workflow A→B→C dry-run + execute, digital twin, org failure scan, integration health, role packs, federation lists, run pause/cancel/rollback routes, agent-interrupt channel, Meson copilot proxy reachability.

Input checklist: [`docs/delivery/AI_ML_OPERATIONAL_GAP_REPORT.md`](../delivery/AI_ML_OPERATIONAL_GAP_REPORT.md)

---

## Operator env scripts

| Vertical | Railway env | Check |
|----------|-------------|-------|
| Legal (Clio) | `npm run clio:fill-env` | `npm run clio:check` |

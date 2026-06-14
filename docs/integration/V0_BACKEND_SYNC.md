# v0 ↔ Backend sync (production-ready)

**Canonical branch:** `main`  
**v0 import branch:** `v0/cesarbohorquezjr-4251-8b623736` (local: `v0-sync`)  
**Cursor branch:** `cursor/auth-config-cli-0dd3`

Keep these branches **fast-forwarded to `main`** so v0 and Cursor always see the same backend + proxy wiring as production.

## Sync branches (after each backend release)

```powershell
git checkout main
git pull origin main

git checkout v0-sync
git merge --ff-only main
git push origin v0-sync:v0/cesarbohorquezjr-4251-8b623736

git checkout cursor/auth-config-cli-0dd3
git merge --ff-only main
git push origin cursor/auth-config-cli-0dd3

git checkout main
```

## Frontend source of truth

- Active UI: `apps/web` (v0 import). See [`FRONTEND_SOURCE_OF_TRUTH.md`](../FRONTEND_SOURCE_OF_TRUTH.md).
- **Do not** edit v0 pages/components in Cursor for backend wiring — use existing `apps/web/lib/api.ts` + Next proxy.
- API traffic: `apps/web/next.config.mjs` rewrites `/api/:path*` → `FASTAPI_BASE_URL` (Railway prod).

## Live backend APIs (Epic I + prod smoke, 2026-06-09)

| Feature | Backend | Next proxy | Client (`lib/api.ts`) |
|---------|---------|------------|------------------------|
| Meson interpret/deploy | `POST /api/meson/interpret`, `/deploy` | explicit routes + rewrite fallback | `mesonApi` |
| Assign task | `POST /api/agent-jobs` | rewrite | `agentJobsApi` |
| Assistant chat | `POST /api/assistant/chat` | `app/api/chat/route.ts` (SSE) | chat transport |
| Workflow dry-run / execute | `POST /api/workflows/dry-run`, `/execute` | rewrite | `workflowsApi` |
| Run detail / pause / cancel | `GET /api/runs/{id}`, `POST …/pause`, `…/cancel` | explicit run routes | `runsApi` |
| Failure predictions | `GET/POST …/failure-predictions/*` | rewrite | `workflowsApi.scanFailurePredictions` |
| CS integration health | `GET/POST /api/enterprise/integration-health*` | rewrite | `enterpriseApi` |
| Role packs | `GET/POST /api/marketplace/role-packs*` | rewrite | `marketplaceApi.listRolePacks` |
| Federation | `/api/federation/*` | rewrite | `federationApi` |
| Run interrupt | `POST /api/agent-interrupts` | explicit route | `agentInterruptsApi` |

## Production verification

```bash
npm run smoke:ai-production   # IMPL 8 + core AI APIs vs Railway
npm run smoke:post-tier5      # enterprise health + role packs catalog
```

Requires `backend/.env.operator.local` with Supabase JWT + service role.

## v0 prompt notes

- [`V0_AI_INTELLIGENCE_PROMPTS.md`](../design/V0_AI_INTELLIGENCE_PROMPTS.md) — UI-only prompts (F1–F4). Meson **interpret/deploy** and agent chat are **live**; suggestion/optimization Meson endpoints remain future work — use mocks only for those.
- Backend gap report: [`AI_ML_OPERATIONAL_GAP_REPORT.md`](../delivery/AI_ML_OPERATIONAL_GAP_REPORT.md)

## Environment (Vercel + Railway)

| Variable | Where | Purpose |
|----------|-------|---------|
| `FASTAPI_BASE_URL` | Vercel | Railway backend (`https://gravitre-saas-backend-production.up.railway.app`) |
| `NEXT_PUBLIC_APP_URL` | Vercel | `https://gravitre.app` |
| Supabase keys | Vercel + Railway | Auth + org context |

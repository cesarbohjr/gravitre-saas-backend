# FE-10 — Workflow Builder + Run Viewer (Wire-Only)

**Authority:** SYSTEM.md, MASTER_PHASED_MODULE_PLAN.md, Gravitre_Brand_Alignment_Spec.md, BE-11 implementation.

## Scope

- **View** workflow definitions (list + detail).
- **Create/edit** workflow definition JSON in a wire-only editor (textarea); no AI builder.
- **Run a dry-run** (POST with inline definition or workflow_id).
- **View a run** and step-by-step outputs/errors.
- **View audit events** related to the run: optional; BE-12 GET /api/audit not implemented in BE-11, so no audit UI in FE-10.

UI and proxy wiring only. No new backend features.

## Non-goals

- No direct FastAPI calls from the browser (all via Next.js API routes).
- No new libraries (textarea for JSON; no Monaco).
- No generation, no agents, no execution (dry-run only).
- No optimistic UI; dry-run results come from API only.

## API Proxy Routes (Server-Only)

All under `app/api/workflows/`. Forward `Authorization` to FastAPI using `FASTAPI_BASE_URL`. Return 500 if `FASTAPI_BASE_URL` is missing; 503 if backend fetch fails. Never log tokens.

| Method | Route | Backend |
|--------|--------|--------|
| GET | `/api/workflows` | GET /api/workflows |
| GET | `/api/workflows/:id` | GET /api/workflows/:id |
| POST | `/api/workflows/dry-run` | POST /api/workflows/dry-run |
| GET | `/api/workflows/runs/:id` | GET /api/workflows/runs/:id |

Optional (not implemented in BE-11): `GET /api/audit?resource_type=workflow_run&resource_id=...`

## UI Routes

| Path | Purpose |
|------|--------|
| `/workflows` | List workflows; link to New workflow and to each definition. |
| `/workflows/new` | Inline definition editor + parameters + Dry run. |
| `/workflows/[id]` | Load definition by id, editor + parameters + Dry run. |
| `/runs/[id]` | Run viewer: run info, steps table, step detail (output/error, collapsible). |

## Data / State

- Loading, empty, and error states on all views.
- If `/api/auth/me` returns `org_id == null`: disable workflow actions and show “Onboarding pending”.
- Token from Supabase session; all API calls use same-origin `/api/*` with `Authorization: Bearer <token>`.

## Brand

- Colors, typography, radii, spacing per Brand Alignment Spec (tokens only; no hardcoded hex).
- Table: token-styled borders and text.
- Status badges: token-based (success, warning, danger, muted).
- Focus states: `focus-visible:ring-2 focus-visible:ring-ring`.

## Endpoints (Backend BE-11)

- `GET /api/workflows` → `{ workflows: [{ id, name, schema_version, updated_at }] }`
- `GET /api/workflows/:id` → workflow detail with `definition` (JSON).
- `POST /api/workflows/dry-run` → body `{ workflow_id?, definition?, parameters? }` → `{ run_id, status, plan, steps, errors }`
- `GET /api/workflows/runs/:id` → run with `steps[]` (step_id, status, output_snapshot, error_code, error_message, is_retryable).

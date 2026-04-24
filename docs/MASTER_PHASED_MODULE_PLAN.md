# Gravitre Master Phased Module Plan

**Status:** Canonical planning artifact  
**Authority:** SYSTEM.md  
**Last updated:** Per repository sync  
**Audience:** Senior Backend, Frontend, and Sys/Admin engineering collaboration

---

## Inputs Used

- `SYSTEM.md` (highest authority)
- `docs/brand/Gravitre_Brand_Alignment_Spec.md` (UI constraints — **sole authority for frontend branding**)
- `packages/design-system/DESIGN_TOKENS_CONTRACT.md` (token contract — *note: may need to be added to repo per structure normalization*)

---

# Part I — Repository Analysis (Mandatory Reconnaissance)

## 1.1 Primary Repository: Gravitre Operator AI

| Area | Status | Details |
|------|--------|---------|
| **Backend** | **Present** | FastAPI app with auth, workflows, approvals, audit, RAG, operators, connectors. |
| **Frontend** | **Present** | Next.js app under `apps/web` with shell + core pages (operator, agents, workflows, connectors, approvals, runs, audit, metrics, RAG). |
| **Sys/Admin** | **Partial** | Supabase migrations and `.env.example` present; deployment/infra not defined. |
| **Design system** | **Partial** | Brand spec + `globals.css` + shadcn/ui present; no standalone design-system package or token exports. |
| **Documentation** | **Present** | `SYSTEM.md`, `docs/MASTER_PHASED_MODULE_PLAN.md`, `docs/brand/Gravitre_Brand_Alignment_Spec.md` exist and are complete. |

**Conclusion:** The repository contains live backend + frontend implementations. The plan’s original “greenfield” assumption is outdated; implementation status must be tracked against actual modules in this repo.

---

## 1.2 External Reference: gravitre_brand_alignment_files

A separate folder (`gravitre_brand_alignment_files`) contains partial design system scaffolding. It is **not** inside the primary repo and must be treated as a reference only.

| Artifact | Present | Brand Spec Compliant? |
|----------|---------|------------------------|
| `globals.css` | Yes | **No** — see drift below |
| `tailwind.config.ts` | Yes | **Partial** — different semantic mapping |
| `theme-class.ts` | Yes | Yes — `.dark` class approach matches |
| `DESIGN_TOKENS_CONTRACT.md` | Yes | Yes |
| `layout.tsx` | No | N/A |
| `package.json` | No | N/A |
| `design/tokens/*.json` | No | N/A |
| shadcn/ui | No | N/A |

**If assets from `gravitre_brand_alignment_files` are merged into the primary repo, they must be aligned to Brand Spec before use.** See §1.4.

---

## 1.3 Implementation Truth Table (Verified)

### Backend (BE)

| Module | Status | Notes |
|--------|--------|-------|
| **BE-00** | **Implemented** | FastAPI, auth, org context, health |
| **BE-01** | **Implemented** | Supabase migrations, naming convention |
| **BE-10** | **Implemented** | RAG retrieval + sources |
| **BE-11** | **Implemented** | Workflows list/detail + dry-run |
| **BE-12** | **Implemented** | Audit events + GET /api/audit |
| **BE-20** | **Implemented** | Execute + approvals |
| **BE-21** | **Partial** | Operator action plan/run exists; no generic `POST /api/operators/:type/confirm` endpoint |
| **BE-30** | **Implemented** | Integrations CRUD via `/api/integrations` (connector-backed) |
| **BE-31** | **Implemented** | Schedules CRUD + rollback endpoint |

### Roles & Membership (RB)

| Module | Status | Notes |
|--------|--------|-------|
| **RB-00** | **Implemented** | Org member endpoints + role constraint migration |

### Data Connectors (DC)

| Module | Status | Notes |
|--------|--------|-------|
| **DC-00** | **Implemented** | Source registration + ingestion API |
| **DC-10** | **Implemented** | Ingestion UI under `/rag` |

### Frontend (FE)

| Module | Status | Notes |
|--------|--------|-------|
| **FE-00** | **Implemented** | Next.js shell + tokens + shadcn |
| **FE-10** | **Implemented** | RAG query UI at `/chat` |
| **FE-11** | **Implemented** | Workflows list/detail + dry-run UI |
| **FE-12** | **Implemented** | Audit UI with filters, table, and pagination |
| **FE-20** | **Implemented** | Runs list + detail with approvals and filters |
| **FE-21** | **Implemented** | Operator console + confirm flow |
| **FE-30** | **Implemented** | Integrations UI + workflow schedules + rollback action |

### Frontend Design Coverage (for v0)

| FE Module | Design Coverage | Notes |
|----------|-----------------|-------|
| **FE-00** | **Spec exists** | `docs/brand/Gravitre_Brand_Alignment_Spec.md` |
| **FE-10** | **Missing** | No RAG query UI spec |
| **FE-11** | **Missing** | No workflows UI spec |
| **FE-12** | **Missing** | No audit/metrics UI spec |
| **FE-20** | **Partial** | Approvals spec exists; runs UI not specified |
| **FE-21** | **Spec exists** | `docs/phase-8/OPERATOR_UI.md` |
| **FE-30** | **Partial** | Connector UI spec exists; integrations/schedules now implemented |

---

## 1.3.1 v0 Prompt — FE Design Coverage

v0 Prompt (paste as-is)

Design the missing Gravitre frontend modules to align with `docs/brand/Gravitre_Brand_Alignment_Spec.md` and the existing app shell. Do not redesign the operator console or existing connector UI. Keep the UI enterprise, minimal, and operational. Reuse current card/table patterns, muted badges, and environment visibility.

Scope (design only):

- **FE-10 — RAG Query UI**: `/chat` (or approved RAG query surface). Provide a structured query workspace (not chatbot bubbles), results list, and source references.
- **FE-11 — Workflows UI**: `/workflows` list + `/workflows/[id]` detail. Include dry-run inputs, validation states, and version list/activation layout consistent with existing patterns.
- **FE-12 — Audit + Metrics**: `/audit` table with filters, severity badges, and empty/error/loading states. `/metrics` overview using cards + small charts where appropriate.
- **FE-20 — Runs UI**: `/runs` list with status/environment badges and `/runs/[id]` detail view with step list, approvals status, and run metadata. Approvals panel should match existing approval UX patterns.
- **FE-30 — Integrations + Schedules**: Integrations list/detail and workflow schedule management. Do not redesign connector cards; extend them for integrations where necessary.

Constraints:
- Preserve navigation grouping and top-bar environment visibility.
- Include admin-only affordances where required.
- All surfaces must show loading, empty, and error states.
- No new side panels or layout changes; follow existing Gravitre shell.

---

## 1.4 Brand Spec Compliance & Drift (Critical for Frontend)

**Authority:** `docs/brand/Gravitre_Brand_Alignment_Spec.md` — deviation is not allowed.

| Spec Requirement | gravitre_brand_alignment_files | Compliant? |
|------------------|--------------------------------|------------|
| **Font** | Manrope | **No** — Spec mandates Inter |
| **Primary CTA** | `--brand-accent` (blue) as secondary | **No** — Spec: Action Blue = primary CTA via `--action` |
| **Highlight** | `--brand-primary` (lime) | **Partial** — Spec: lime = `--highlight`, not primary |
| **Semantic vars** | `--bg-canvas`, `--text-strong`, etc. | **No** — Spec requires `--bg`, `--surface`, `--text`, `--action`, `--highlight` |
| **Tailwind mapping** | `colors.background`, `colors.foreground` | **No** — Spec: `background = --bg`, `primary = --action`, etc. |
| **Radius** | 6, 8, 12, 16, 20, 30px | **No** — Spec: 10, 12, 16, 20px only |
| **Theme mechanism** | `.dark` on html | Yes |
| **shadcn/ui** | Not installed | **No** — Spec requires shadcn/ui |

**Backend assessment:** N/A — Brand Spec constrains frontend only.

**Sys/Admin assessment:** Brand Spec has no platform implications.

**Frontend implementation rule:** FE-00 and all FE modules must implement exactly to Brand Spec. Do not copy token names or values from `gravitre_brand_alignment_files` without mapping to Spec semantics.

---

## 1.5 Risks & Constraints

- **Risk:** No `design/tokens/*.json` files exist. FE-00 depends on token values for `globals.css`. **Mitigation:** Define minimal token set in Spec/Contract; implement directly in `globals.css` until Figma exports exist.
- **Risk:** Org model (Supabase Organizations vs custom tables) unresolved. **Mitigation:** Document in Open Questions; block BE-00 completion until decided.
- **Risk:** Workflow definition schema undefined. **Mitigation:** Block BE-11 until schema is specified.
- **Constraint:** No new dependencies without explicit authorization (per Cursor Build Rules).
- **Constraint:** No feature invention—only modules in this plan.

---

# Part II — Cross-Functional Contracts & Dependencies

## 2.1 Backend ↔ Frontend

| Contract | Owner | Consumer | Specification |
|----------|-------|----------|---------------|
| Auth context | BE-00 | FE-00, FE-10+ | JWT in header; `GET /api/auth/me` returns `{ user_id, org_id?, email? }` |
| RAG retrieve | BE-10 | FE-10 | `POST /api/rag/retrieve` → `{ chunks, query_id }` |
| Workflows list/detail | BE-11 | FE-11 | `GET /api/workflows`, `GET /api/workflows/:id` |
| Workflow dry-run | BE-11 | FE-11 | `POST /api/workflows/dry-run` → `{ valid, steps, errors? }` |
| Audit events | BE-12 | FE-12 | `GET /api/audit` with query params |
| Workflow execute | BE-20 | FE-20 | `POST /api/workflows/:id/execute`, `GET /api/workflows/runs/:run_id` |
| Operator confirm | BE-21 | FE-21 | `POST /api/operators/:type/confirm` |
| Integrations CRUD | BE-30 | FE-30 | `GET/POST /api/integrations` |
| Schedules CRUD | BE-31 | FE-30 | `POST /api/workflows/:id/schedules`, `GET /api/workflows/runs` |

**Frontend must not:** Optimistically update UI before backend confirmation. Use loading/error/empty states; no misleading success.

**Backend must not:** Return 200 with partial failure. Use explicit error codes and request_id in logs.

---

## 2.2 Backend ↔ Sys/Admin

| Dependency | Backend Module | Sys/Admin Deliverable |
|------------|----------------|------------------------|
| Supabase URL + keys | BE-00 | SA-00: env vars, secrets management |
| Postgres connection | BE-00, all BE | SA-00: Supabase project, connection pooling |
| Migration execution | BE-01, BE-10+ | SA-00: migration runner (Supabase CLI or equivalent) |
| pgvector extension | BE-10 | SA-00: enable in Supabase project |
| Audit log retention | BE-12 | SA-00: retention policy (document; automation optional) |
| Credential encryption | BE-30 | SA-00: Supabase Vault or app-level encryption strategy |

**Sys/Admin must not:** Expose secrets in logs, migrations, or config committed to repo.

**Backend must not:** Hardcode connection strings or API keys.

---

## 2.3 Frontend ↔ Sys/Admin

| Constraint | Frontend Expectation | Sys/Admin Deliverable |
|------------|---------------------|------------------------|
| API base URL | Frontend calls `/api/*` or env-defined base | SA-00: CORS, reverse proxy, or same-origin Next.js API routes proxying to FastAPI |
| Build artifacts | Static export or SSR | SA-00: deployment target compatibility (Vercel, Docker, etc.) |
| Env at build time | `NEXT_PUBLIC_*` for client | SA-00: env injection strategy; no secrets in client bundle |

**Frontend must not:** Embed API keys or backend URLs that differ per environment without env vars.

---

# Part III — Explicit Non-Goals

- Do not add features, pages, workflows, or operators beyond SYSTEM.md and this plan.
- Do not introduce new UI libraries beyond shadcn/ui + Radix.
- Do not introduce new fonts; Inter only.
- Do not refactor business logic that does not exist.
- Do not create placeholder or stub modules that obscure missing implementation.
- Do not merge `gravitre_brand_alignment_files` without Brand Spec alignment.
- Do not implement Phase N+1 before Phase N acceptance criteria are met.

---

## Deferred / Not in SYSTEM.md Scope (Requires Explicit Authorization)

The following are **not** included in this plan because SYSTEM.md does not explicitly require them:

- Integrations registry (catalog of external systems)
- Multi-tenant department/team hierarchy beyond org
- Custom operator authoring UI
- Real-time collaboration / presence
- Notifications / alerting infrastructure
- API rate limiting / quotas
- SSO / SAML / OIDC (beyond Supabase Auth)

---

# Phase 0 — Foundation / Baseline

**Phase intent:** Establish runnable baseline: repo structure, config, auth, design tokens, logging. No product features.

**Execution order:** SA-00 (platform) → BE-00, BE-01 (backend) and FE-00 (frontend) may proceed in parallel after SA-00.

**Allowed behaviors:**
- Monorepo structure (apps/web, packages/design-system, design/tokens)
- Environment configuration (env vars, Supabase project wiring)
- Supabase Auth setup (sign-in, sign-out, session)
- Design token pipeline (JSON → globals.css)
- Structured logging scaffold (request IDs, error codes)
- Database migration tooling and conventions

**Forbidden behaviors:**
- Product pages beyond minimal layout/placeholder
- RAG, workflows, or operator logic
- Any writes beyond auth/session

---

## Module ID: SA-00 — Platform Foundation (Sys/Admin)

- **Purpose:** Establish Supabase project, environment strategy, secrets handling, and operational baseline. All BE/FE modules depend on this.

- **In scope:**
  - Supabase project creation (or use existing)
  - Environment strategy: `.env.example` with required vars; no secrets in repo
  - Secrets: Supabase anon key, service role key, API keys (OpenAI, etc.) via env or Supabase Vault
  - CORS configuration for FastAPI (allow Next.js origin)
  - Migration folder: `supabase/migrations/` with naming convention
  - pgvector extension enabled (for Phase 1 RAG)
  - Backup/restore expectations documented (Supabase managed)

- **Out of scope:**
  - CI/CD pipelines
  - Kubernetes / container orchestration
  - Custom observability (logging scaffold is BE-00)

- **Deliverables:**
  - `.env.example` with `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY?`
  - Supabase project with database and Auth enabled
  - Migration runner executable (`supabase db push` or equivalent)
  - One-line doc: "How to run locally"

- **Dependencies:**
  - Internal: none
  - External: Supabase account, Supabase CLI

- **Acceptance criteria:**
  - [ ] Developer can `supabase start` (or connect to project) and run migrations
  - [ ] No secrets in git
  - [ ] pgvector available

- **Stop conditions:**
  - Supabase vs self-hosted Postgres — assume Supabase unless stated otherwise

---

## Module ID: BE-00 — Foundation & Auth Baseline

- **Purpose:** Provide FastAPI app skeleton, Supabase Auth integration, env/config loading, and structured logging. Org-scoped access primitives.

- **In scope:**
  - FastAPI app entrypoint
  - Supabase client initialization (env-based URL/key)
  - Auth middleware (validate JWT, attach user/org to request context)
  - Health check endpoint
  - Structured logging (request_id, user_id, org_id, error codes)
  - CORS and security headers

- **Out of scope:**
  - User registration UI (use Supabase Auth hosted or minimal custom)
  - Org creation UI
  - RLS policy implementation (Phase 1 modules)

- **Endpoints / Contracts:**
  - `GET /health` → `{ status, version?, timestamp }`
  - `GET /api/auth/me` → `{ user_id, org_id?, email? }` (requires auth)

- **Supabase / DB:**
  - Tables: `organizations` (if not using Supabase built-in)
    - `id`, `name`, `created_at`, `updated_at`
  - `organization_members` (if custom)
    - `id`, `org_id`, `user_id`, `role`, `created_at`
  - *Decision required:* Use Supabase Organizations (beta) or custom tables. If custom:
    - Migrations: `YYYYMMDDHHMMSS_create_organizations.sql`, `_create_organization_members.sql`
    - Indexes: `org_id`, `user_id` on members
  - RLS: org-scoped; `user_id` / `org_id` from JWT or join
  - Audit fields: `created_at`, `updated_at`, `created_by` (where applicable)

- **Services / Wiring:**
  - `app/main.py` — FastAPI app, routers
  - `app/config.py` — env loading (pydantic-settings)
  - `app/auth/` — middleware, dependencies (get_current_user, get_org_context)
  - `app/core/logging.py` — structured logger
  - Flow: middleware → auth dependency → controller → (service if needed)

- **Dependencies:**
  - Internal: SA-00 (Supabase project, env vars)
  - External: FastAPI, Supabase Python client, python-dotenv, pydantic-settings

- **Error handling:**
  - 401: missing/invalid token
  - 403: no org context / insufficient permission
  - 500: generic with request_id in response and logs

- **Audit / traces:**
  - Log: request_id, method, path, user_id, org_id, status_code, duration_ms
  - Do not persist audit rows yet (Phase 2)

- **Acceptance criteria:**
  - [ ] `/health` returns 200 without auth
  - [ ] `/api/auth/me` returns 401 without valid JWT
  - [ ] `/api/auth/me` returns user/org with valid JWT
  - [ ] Logs include request_id and user context

- **Stop conditions:**
  - Org model undefined (Supabase vs custom)
  - Auth provider choices (email/password, magic link, etc.) — document and proceed with one

---

## Module ID: BE-01 — Database Migration & Conventions

- **Purpose:** Establish migration tooling and naming conventions for Supabase/Postgres.

- **In scope:**
  - Migration runner (Supabase CLI `supabase migration` or custom)
  - Naming: `YYYYMMDDHHMMSS_description.sql`
  - Seed script placeholder (optional, for dev)
  - Convention doc: all tables have `created_at`, `updated_at`; org-scoped tables have `org_id`

- **Out of scope:**
  - Migrations for Phase 1+ tables (separate modules)
  - Data seeding for production

- **Endpoints / Contracts:** N/A (tooling only)

- **Supabase / DB:**
  - Migrations folder: `supabase/migrations/` (or project-conventional path)
  - Every migration is reversible where feasible (document rollback steps)

- **Services / Wiring:** N/A

- **Dependencies:**
  - Internal: SA-00 (migration runner, migrations folder)
  - External: Supabase CLI, PostgreSQL

- **Error handling:** Migration failures must fail build/apply; no silent drift.

- **Audit / traces:** Log migration apply/rollback.

- **Acceptance criteria:**
  - [ ] `supabase db push` (or equivalent) runs without error
  - [ ] New migration file can be added and applied

- **Stop conditions:**
  - Migration tool choice (Supabase CLI vs Alembic vs custom) — decide and document

---

## Module ID: FE-00 — Foundation & Design System Wiring

> **Frontend Authority:** This module MUST implement exactly to `docs/brand/Gravitre_Brand_Alignment_Spec.md`. No deviation. See Part I §1.4 for drift notes on external reference assets.

- **Purpose:** Next.js app scaffold with design tokens, Tailwind, shadcn/ui, and minimal root layout. No product pages.

- **In scope:**
  - `apps/web` structure: `app/`, `styles/`
  - `app/layout.tsx` — root layout, **Inter** font via `next/font/google` (Brand Spec §2.1), CSS variable `--font-sans`
  - `app/styles/globals.css` — semantic CSS vars per Brand Spec §3.2: `--bg`, `--surface`, `--surface-2`, `--text`, `--text-muted`, `--action`, `--action-hover`, `--action-pressed`, `--focus`, `--highlight`, `--border`, `--border-strong`, `--success`, `--warning`, `--danger`
  - Tailwind config — Brand Spec §3.3: `colors.background = hsl(var(--bg))`, `colors.primary = hsl(var(--action))`, etc.
  - shadcn/ui installed (Button, Card, Input, etc.)
  - Theme switching: `.dark` on `<html>` (Brand Spec §3.4)
  - Radius: 10px, 12px, 16px, 20px only (Brand Spec §4.1)
  - Minimal placeholder route: `/`

- **Out of scope:**
  - Auth UI components (sign-in form, etc.) — can be Supabase hosted or minimal
  - Product routes (chat, workflows, etc.)
  - New token values (use existing from `design/tokens/`)

- **Routes / Screens:**
  - `/` — placeholder; optional sign-in link; empty state
  - `/login` — redirect to Supabase Auth or minimal form (decision: hosted vs custom)

- **Data wiring:**
  - Optional: `GET /api/auth/me` for session check
  - Loading: skeleton or spinner; Error: inline message; Empty: N/A for placeholder

- **Component requirements:**
  - shadcn/ui: Button, Card (if placeholder uses card)
  - All colors via `hsl(var(--...))` — no hardcoded hex
  - Inter only; type scale per Brand Spec (H1–Micro)

- **State management:**
  - Session: server-side or React Context (minimal); no global state lib required

- **Accessibility:**
  - Semantic HTML; focus visible; basic ARIA where needed

- **Acceptance criteria:**
  - [ ] App builds and runs
  - [ ] Light/dark theme toggle works
  - [ ] No hardcoded colors in components
  - [ ] Inter font applied globally

- **Stop conditions:**
  - Token JSON files missing at `design/tokens/` — must exist or be created before wiring
  - Theme mechanism inconsistent with Brand Spec — confirm `data-theme` vs `.dark`

---

# Phase 1 — Generate & Draft

**Phase intent:** Read-only access to approved sources; drafting artifacts; workflow dry-runs; non-destructive operator assistance.

**Allowed behaviors:**
- RAG retrieval from approved sources; cited answers
- Workflow preview / dry-run (no execution)
- Draft generation (summaries, artifacts)
- Operator recommendations (no writes)
- Read-only audit/trace view

**Forbidden behaviors:**
- Any persistent writes except drafts (ephemeral or explicitly draft-scoped)
- Workflow execution with side effects
- External system calls
- Operator actions that modify data

---

## Module ID: BE-10 — RAG Ingestion & Retrieval (Read-Only)

- **Purpose:** Ingest documents into vector store; expose retrieval API for grounded, cited answers. Phase 1: read-only.

- **In scope:**
  - Document ingestion pipeline (approved sources → chunk → embed → store)
  - Retrieval API: query → top-k chunks + metadata
  - Citation requirement: return source IDs, titles, snippets
  - Supabase pgvector (or equivalent) for embeddings

- **Out of scope:**
  - Real-time ingestion UI
  - Feedback loops (thumbs up/down)
  - Multi-model routing
  - Cross-org source sharing

- **Endpoints / Contracts:**
  - `POST /api/rag/retrieve` → request: `{ query, top_k?, org_id }`; response: `{ chunks: [{ id, text, source_id, title, score }], query_id }`
  - `POST /api/rag/ingest` (admin/internal) → request: `{ source_id, chunks }`; response: `{ status, chunks_ingested }`
  - *Decision:* Public ingest or internal-only for Phase 1 — assume internal-only

- **Supabase / DB:**
  - Tables: `sources`, `chunks`, `embeddings` (or unified)
    - `sources`: `id`, `org_id`, `title`, `type`, `created_at`, `updated_at`
    - `chunks`: `id`, `source_id`, `content`, `metadata`, `created_at`
    - `embeddings`: `chunk_id`, `embedding` (vector), `model_version`
  - Indexes: HNSW/IVFFlat on embedding; `org_id`, `source_id`
  - RLS: org-scoped; SELECT only for retrieval; INSERT for ingest (restricted)
  - Migrations: `*_create_rag_tables.sql`

- **Services / Wiring:**
  - `app/rag/retrieval.py` — query, embed, search, format response
  - `app/rag/ingest.py` — chunk, embed, upsert
  - `app/rag/embedding.py` — embedding model client (OpenAI or local)
  - Flow: controller → retrieval service → db

- **Dependencies:**
  - Internal: BE-00 (auth, org context)
  - External: OpenAI API (or local embed model), pgvector

- **Error handling:**
  - 400: invalid query
  - 404: no sources for org
  - 503: embedding service unavailable
  - Fallback: return empty chunks + message "No results"; never hallucinate

- **Audit / traces:**
  - Log: query_id, org_id, query_hash, result_count, latency_ms
  - No hallucinated answers: if retrieval fails, return empty with explicit message

- **Acceptance criteria:**
  - [ ] Retrieve returns chunks with source_id, title, snippet
  - [ ] Empty query or no sources returns structured empty response
  - [ ] RLS prevents cross-org access

- **Stop conditions:**
  - Chunking strategy undefined (size, overlap)
  - Embedding model choice — document and proceed with one
  - Approved sources definition — where does the list live? (DB table `sources` assumed)

---

## Module ID: BE-11 — Workflow Dry-Run (Preview)

- **Purpose:** Allow workflow definition to be validated and previewed without execution. No side effects.

- **In scope:**
  - Workflow definition schema (JSON/YAML structure)
  - Dry-run endpoint: validate definition, return simulated step output (stub or real for idempotent reads)
  - List workflows (read-only)

- **Out of scope:**
  - Workflow execution
  - Trigger scheduling
  - External integrations execution

- **Endpoints / Contracts:**
  - `GET /api/workflows` → `{ workflows: [{ id, name, status, updated_at }] }`
  - `POST /api/workflows/dry-run` → request: `{ definition }`; response: `{ valid, steps: [{ name, status, preview_output? }], errors? }`
  - `GET /api/workflows/:id` → workflow definition + metadata (read-only)

- **Supabase / DB:**
  - Tables: `workflows`
    - `id`, `org_id`, `name`, `definition` (JSONB), `created_at`, `updated_at`, `created_by`
  - RLS: org-scoped SELECT; Phase 1 no INSERT via API (manual seed or later module)
  - Migrations: `*_create_workflows.sql`

- **Services / Wiring:**
  - `app/workflows/schema.py` — definition validation
  - `app/workflows/dry_run.py` — step-by-step preview (no writes)
  - `app/workflows/repository.py` — CRUD (read-only for Phase 1 API)

- **Dependencies:**
  - Internal: BE-00
  - External: none (or minimal workflow DSL parser)

- **Error handling:**
  - 400: invalid definition
  - 404: workflow not found

- **Audit / traces:**
  - Log dry-run invocations: workflow_id, org_id, user_id, result (valid/invalid)

- **Acceptance criteria:**
  - [ ] Dry-run returns valid/invalid + step preview
  - [ ] List workflows returns org-scoped results only

- **Stop conditions:**
  - Workflow definition schema not defined — must specify before implementation
  - Dry-run semantics: stub vs real read-only step execution — decide

---

## Module ID: BE-12 — Audit / Trace Log (Read-Only)

- **Purpose:** Persist and expose audit events for Phase 1. Read-only API.

- **In scope:**
  - Audit event schema (action, actor, resource, timestamp, metadata)
  - Write path: internal only (from other services)
  - Read API: filter by org, time range, action type

- **Out of scope:**
  - Retention policy automation
  - Export (CSV, etc.)
  - Real-time streaming

- **Endpoints / Contracts:**
  - `GET /api/audit` → query params: `org_id`, `from`, `to`, `action?`, `limit`; response: `{ events: [{ id, action, actor_id, resource, timestamp, metadata }] }`

- **Supabase / DB:**
  - Tables: `audit_events`
    - `id`, `org_id`, `action`, `actor_id`, `resource_type`, `resource_id`, `metadata` (JSONB), `created_at`
  - Indexes: `org_id`, `created_at`, `action`
  - RLS: org-scoped SELECT only; INSERT via service role or trigger
  - Migrations: `*_create_audit_events.sql`

- **Services / Wiring:**
  - `app/audit/repository.py` — insert, query
  - `app/audit/types.py` — event schema
  - Other modules call `audit.log(event)` internally

- **Dependencies:**
  - Internal: BE-00
  - External: none

- **Error handling:**
  - 400: invalid date range or params

- **Audit / traces:**
  - Audit module itself logs to stdout; events in DB

- **Acceptance criteria:**
  - [ ] Events can be inserted by services
  - [ ] Read API returns org-scoped, paginated events

- **Stop conditions:**
  - Event schema (action enum, required fields) — define before implementation

---

## Module ID: FE-10 — RAG Query Interface (Chat Workstation)

- **Purpose:** UI for users to pose questions and receive grounded, cited answers from RAG. Read-only.

- **In scope:**
  - Query input + submit
  - Response display with citations (source, title, link/snippet)
  - Loading and empty states
  - Error state (no results, service error)
  - Org-scoped; no conversation persistence in Phase 1 (or ephemeral session only)

- **Out of scope:**
  - Multi-turn conversation history persistence
  - Source management UI
  - Feedback buttons
  - Streaming (optional; if added, document)

- **Routes / Screens:**
  - `/chat` or `/query` — main RAG query interface
  - Empty: "Ask a question to get started"
  - Loading: skeleton or spinner
  - Error: "Unable to retrieve results. Try again."

- **Data wiring:**
  - `POST /api/rag/retrieve` — on submit
  - Pass org_id from auth context

- **Component requirements:**
  - shadcn/ui: Input, Button, Card, ScrollArea
  - Citations: Card or list with source metadata
  - Tokens only; no hardcoded colors

- **State management:**
  - Local component state for query, results, loading, error
  - Optional: ephemeral session storage for current session only

- **Accessibility:**
  - Labeled inputs; focus management; cite links keyboard-accessible

- **Acceptance criteria:**
  - [ ] User can submit query and see cited results
  - [ ] Empty/error states display correctly
  - [ ] Citations show source and snippet

- **Stop conditions:**
  - Conversation persistence decision (ephemeral vs DB) — Phase 1 assumes ephemeral or none

---

## Module ID: FE-11 — Workflow Dry-Run UI

- **Purpose:** UI to view workflows and run dry-run preview. No execution.

- **In scope:**
  - List workflows (read-only)
  - Dry-run form: paste or select definition → run preview
  - Display validation result + step preview
  - Empty state: no workflows

- **Out of scope:**
  - Workflow editor (visual or YAML)
  - Execute button
  - Schedule configuration

- **Routes / Screens:**
  - `/workflows` — list
  - `/workflows/[id]` — detail + dry-run
  - Empty: "No workflows yet"
  - Loading/error: standard patterns

- **Data wiring:**
  - `GET /api/workflows`, `GET /api/workflows/:id`, `POST /api/workflows/dry-run`

- **Component requirements:**
  - shadcn/ui: Table or Card list, Button, Textarea (for definition input), Badge
  - Tokens only

- **State management:**
  - Server state for list; local for dry-run result

- **Accessibility:**
  - Table semantics; form labels

- **Acceptance criteria:**
  - [ ] User can list workflows and run dry-run
  - [ ] Dry-run result displays validation + step preview

- **Stop conditions:**
  - Workflow definition input: paste JSON vs form — decide UX

---

## Module ID: FE-12 — Audit Log View (Read-Only)

- **Purpose:** Read-only view of audit events for org.

- **In scope:**
  - List events with filters (date range, action type)
  - Pagination
  - Basic columns: timestamp, action, actor, resource

- **Out of scope:**
  - Export
  - Real-time refresh
  - Detail drill-down (optional for Phase 1)

- **Routes / Screens:**
  - `/audit` — event list
  - Empty: "No events in this range"
  - Loading/error: standard

- **Data wiring:**
  - `GET /api/audit` with query params

- **Component requirements:**
  - shadcn/ui: Table, Select (filters), Button
  - Tokens only

- **State management:**
  - Server state with client-side filter state

- **Accessibility:**
  - Table semantics; filter labels

- **Acceptance criteria:**
  - [ ] User can filter and paginate audit events
  - [ ] Events display with timestamp, action, actor, resource

- **Stop conditions:** None specific

---

# Phase 2 — Assisted Execution

**Phase intent:** Internal writes with explicit user intent; approvals before sensitive actions; clear audit trails.

**Allowed behaviors:**
- Workflow execution (internal systems only)
- Operator-assisted writes (with user confirmation)
- Approval flows before sensitive actions
- Persistent draft storage
- Full audit logging

**Forbidden behaviors:**
- External system writes (APIs, webhooks to third parties)
- Unattended/scheduled execution
- Operator autonomy without user confirmation

---

## Module ID: BE-20 — Workflow Execution (Internal)

- **Purpose:** Execute workflows with side effects limited to internal DB and services. User intent required per run.

- **In scope:**
  - Execute workflow by ID
  - Step execution with internal writes (DB, internal API)
  - Audit each step
  - Rollback or compensation where feasible (document)

- **Out of scope:**
  - External HTTP/webhook calls
  - Scheduled triggers
  - Parallel fan-out (keep sequential for Phase 2)

- **Endpoints / Contracts:**
  - `POST /api/workflows/:id/execute` → request: `{ parameters? }`; response: `{ run_id, status, steps: [{ name, status, output? }] }`
  - `GET /api/workflows/runs/:run_id` → run status + step details
  - `POST /api/workflows/:id/execute/approve` (if approval required) → same as execute after approval check

- **Supabase / DB:**
  - Tables: `workflow_runs`, `workflow_run_steps`
    - `workflow_runs`: `id`, `workflow_id`, `org_id`, `triggered_by`, `status`, `created_at`, `completed_at`
    - `workflow_run_steps`: `id`, `run_id`, `step_name`, `status`, `input`, `output`, `created_at`
  - RLS: org-scoped
  - Migrations: `*_create_workflow_runs.sql`

- **Services / Wiring:**
  - `app/workflows/executor.py` — run workflow, execute steps
  - `app/workflows/approval.py` — check approval requirement, record approval
  - `app/audit/` — log execution events
  - Flow: controller → executor → step handlers → db, audit

- **Dependencies:**
  - Internal: BE-11, BE-12, BE-00
  - External: same as Phase 1

- **Error handling:**
  - 403: approval required and not granted
  - 409: workflow already running (if concurrency restricted)
  - 500: step failure with run_id and step name in response
  - Compensation: document per-step rollback; implement where trivial

- **Audit / traces:**
  - Log: run_id, workflow_id, org_id, user_id, status, step outcomes
  - Persist to `audit_events` for each execution start/complete

- **Acceptance criteria:**
  - [ ] Execute runs workflow and records steps
  - [ ] Audit events created for execution
  - [ ] Approval flow blocks execution when required

- **Stop conditions:**
  - Approval flow definition (which workflows need approval, who approves)
  - Step handler registry — how are step types mapped to handlers?

---

## Module ID: BE-21 — Operator-Assisted Writes

- **Purpose:** Operators can suggest writes; user must confirm before persistence. Assistive, not autonomous.

- **In scope:**
  - Operator recommendation API (returns suggested action + payload)
  - Confirmation endpoint: user confirms → execute write
  - Supported actions: create/update internal resources (e.g., draft, workflow parameter)
  - Documented journey required per operator type

- **Out of scope:**
  - Operator-invoked external writes
  - Autonomous execution
  - New operator types without journey doc

- **Endpoints / Contracts:**
  - `POST /api/operators/:type/recommend` → request: `{ context }`; response: `{ recommendation: { action, payload, rationale } }`
  - `POST /api/operators/:type/confirm` → request: `{ recommendation_id, confirmed }`; response: `{ status, result? }`
  - Journey docs: stored in `docs/operators/<type>.md` or equivalent

- **Supabase / DB:**
  - Tables: `operator_recommendations`
    - `id`, `org_id`, `operator_type`, `context` (JSONB), `recommendation` (JSONB), `status`, `confirmed_by`, `created_at`
  - RLS: org-scoped
  - Migrations: `*_create_operator_recommendations.sql`

- **Services / Wiring:**
  - `app/operators/dispatcher.py` — route to operator by type
  - `app/operators/<type>/` — per-operator logic (journey-driven)
  - `app/operators/confirmation.py` — validate and execute confirmed action
  - Flow: recommend → (user) → confirm → execute → audit

- **Dependencies:**
  - Internal: BE-00, BE-12
  - External: RAG (BE-10) if operator uses retrieval

- **Error handling:**
  - 400: invalid confirmation (expired, already processed)
  - 404: recommendation not found
  - 422: operator type unknown or journey missing

- **Audit / traces:**
  - Log every recommendation and confirmation
  - Persist to audit_events

- **Acceptance criteria:**
  - [ ] Recommend returns suggestion; confirm executes only after user approval
  - [ ] Operator types have journey docs
  - [ ] Audit trail for recommend + confirm

- **Stop conditions:**
  - Which operator types exist in Phase 2? (e.g., "draft-assistant", "workflow-param-suggester") — list required
  - Journey format and location — define

---

## Module ID: FE-20 — Workflow Execution UI

- **Purpose:** UI to trigger workflow execution, view runs, and handle approval.

- **In scope:**
  - Execute button (with confirmation dialog)
  - Approval flow UI when required (approve/reject)
  - Run history + status
  - Step-level detail view

- **Out of scope:**
  - Workflow definition editor
  - Schedule UI

- **Routes / Screens:**
  - `/workflows/[id]` — add Execute button, run history
  - `/workflows/runs/[run_id]` — run detail
  - Approval modal/dialog when needed

- **Data wiring:**
  - `POST /api/workflows/:id/execute`, `GET /api/workflows/runs/:run_id`, approval endpoint

- **Component requirements:**
  - shadcn/ui: Button, Dialog, Table, Badge
  - Tokens only

- **State management:**
  - Server state for runs; local for modal

- **Accessibility:**
  - Dialog focus trap; confirm/cancel semantics

- **Acceptance criteria:**
  - [ ] User can execute workflow and see run status
  - [ ] Approval flow presents and submits correctly

- **Stop conditions:** None specific

---

## Module ID: FE-21 — Operator Confirmation UI

- **Purpose:** UI to display operator recommendations and confirm/reject.

- **In scope:**
  - Recommendation display (rationale, payload summary)
  - Confirm / Reject buttons
  - Success/error feedback

- **Out of scope:**
  - Operator invocation (may be contextual in RAG or workflow UI)
  - Recommendation history list

- **Routes / Screens:**
  - May be embedded in `/chat` or `/workflows` as modal/sidebar
  - Or `/operators/confirm/[id]` — dedicated confirmation page

- **Data wiring:**
  - `POST /api/operators/:type/confirm` with recommendation_id and confirmed=true/false

- **Component requirements:**
  - shadcn/ui: Card, Button, Alert
  - Tokens only

- **State management:**
  - Local; parent may pass recommendation as prop

- **Accessibility:**
  - Clear action labels; confirm secondary to reject (destructive)

- **Acceptance criteria:**
  - [ ] User can confirm or reject recommendation
  - [ ] Result feedback displayed

- **Stop conditions:** None specific

---

# Phase 3 — Trusted Automation

**Phase intent:** External system writes; scheduled/background execution; strong observability and rollback.

**Allowed behaviors:**
- External API/webhook calls
- Scheduled workflow triggers
- Background jobs
- Rollback/compensation tooling

**Forbidden behaviors:**
- Autonomous goal-setting
- Unaudited external writes
- No rollback path for critical actions

---

## Module ID: BE-30 — External Integrations & Writes

- **Purpose:** Enable workflows to call external APIs and webhooks. Audited and with safeguards.

- **In scope:**
  - Integration config storage (credentials, endpoints) — encrypted
  - Step type: HTTP request, webhook
  - Rate limiting and timeouts
  - Full audit of external calls

- **Out of scope:**
  - OAuth token refresh automation (manual or separate)
  - Custom integration SDKs

- **Endpoints / Contracts:**
  - `GET/POST /api/integrations` — CRUD for integration config (admin)
  - Workflow steps reference integration by ID
  - Execution: executor calls integration service → HTTP

- **Supabase / DB:**
  - Tables: `integrations`
    - `id`, `org_id`, `name`, `type`, `config_encrypted`, `created_at`, `updated_at`
  - RLS: org-scoped
  - Migrations: `*_create_integrations.sql`
  - Audit: every external call logged

- **Services / Wiring:**
  - `app/integrations/client.py` — HTTP executor with timeout/retry
  - `app/integrations/registry.py` — resolve config by ID
  - `app/workflows/executor.py` — extend to handle external step type

- **Dependencies:**
  - Internal: BE-20
  - External: HTTP client (httpx)

- **Error handling:**
  - Timeout, 4xx, 5xx → fail step, log, optional retry
  - Never expose raw credentials in logs

- **Audit / traces:**
  - Log: integration_id, endpoint (redacted), status, latency
  - Persist to audit_events

- **Acceptance criteria:**
  - [ ] Workflow can invoke external HTTP endpoint
  - [ ] All calls audited
  - [ ] Credentials not logged

- **Stop conditions:**
  - Credential encryption approach (Supabase Vault vs app-level)
  - Integration config schema — define per integration type

---

## Module ID: BE-31 — Scheduled Execution & Observability

- **Purpose:** Schedule workflow runs; provide observability and rollback tooling.

- **In scope:**
  - Scheduler (cron-like or Supabase pg_cron)
  - Workflow runs triggered by schedule
  - Run history with filters and search
  - Rollback: manual trigger or documented procedure per workflow type

- **Out of scope:**
  - Visual schedule builder
  - Event-driven triggers (webhook ingestion)

- **Endpoints / Contracts:**
  - `POST /api/workflows/:id/schedules` — create schedule (cron expr)
  - `GET /api/workflows/runs` — list with filters (status, workflow, date)
  - `POST /api/workflows/runs/:id/rollback` — initiate rollback (where supported)
  - `GET /api/workflows/runs/:id` — full detail including step I/O

- **Supabase / DB:**
  - Tables: `workflow_schedules`
    - `id`, `workflow_id`, `cron_expression`, `enabled`, `next_run_at`, `created_at`
  - Extend `workflow_runs` with `trigger_type` (manual, schedule)
  - Migrations: `*_create_workflow_schedules.sql`

- **Services / Wiring:**
  - `app/workflows/scheduler.py` — evaluate cron, enqueue runs
  - `app/workflows/rollback.py` — execute rollback per workflow definition
  - Background worker or pg_cron to trigger scheduler

- **Dependencies:**
  - Internal: BE-20
  - External: pg_cron or external scheduler (e.g., Inngest, Trigger.dev)

- **Error handling:**
  - Schedule eval failure → log, skip, retry next cycle
  - Rollback failure → alert, log, manual intervention

- **Audit / traces:**
  - Log all scheduled triggers and rollbacks
  - Persist to audit_events

- **Acceptance criteria:**
  - [ ] Workflow runs on schedule
  - [ ] Run history queryable
  - [ ] Rollback path documented and executable

- **Stop conditions:**
  - Scheduler choice (pg_cron vs external) — decide
  - Rollback semantics per workflow type — document

---

## Module ID: FE-30 — Integrations & Schedule Management UI

- **Purpose:** UI to manage integration configs and workflow schedules. Observability views.

- **In scope:**
  - List integrations; add/edit (form)
  - List schedules; add/edit cron
  - Run history with filters and drill-down
  - Rollback button (with confirmation) where supported

- **Out of scope:**
  - Credential value display (masked only)
  - Advanced observability (metrics, traces)

- **Routes / Screens:**
  - `/integrations` — list, create, edit
  - `/workflows/[id]/schedules` — schedule list, create
  - `/workflows/runs` — run history
  - `/workflows/runs/[id]` — run detail, rollback

- **Data wiring:**
  - Integrations CRUD, schedules CRUD, runs list/detail, rollback API

- **Component requirements:**
  - shadcn/ui: Table, Form, Input, Button, Badge, Select
  - Tokens only

- **State management:**
  - Server state; optimistic updates where safe

- **Accessibility:**
  - Form labels; destructive action confirmation

- **Acceptance criteria:**
  - [ ] User can manage integrations and schedules
  - [ ] Run history and rollback accessible

- **Stop conditions:** None specific

---

# Part IV — Open Questions (Decisions Required)

| ID | Question | Blocks | Owner |
|----|----------|--------|-------|
| OQ-1 | Org model: Supabase Organizations (beta) vs custom `organizations` + `organization_members` tables? | BE-00 | Product / Platform |
| OQ-2 | Auth provider: email/password, magic link, or both? Document and proceed with one. | BE-00 | Product |
| OQ-3 | Workflow definition schema: JSON structure, step types, validation rules? | BE-11 | Backend |
| OQ-4 | Dry-run semantics: stub output vs real read-only step execution? | BE-11 | Backend |
| OQ-5 | Audit event schema: action enum values, required metadata fields? | BE-12 | Backend |
| OQ-6 | Token JSON: use Figma exports from `design/tokens/` or define minimal set in `globals.css` until exports exist? | FE-00 | Frontend |
| OQ-7 | Phase 2 operator types: which operators (e.g., draft-assistant, workflow-param-suggester)? | BE-21 | Product |
| OQ-8 | Journey doc format and location for operators? | BE-21 | Backend |
| OQ-9 | Credential encryption resolved: Supabase Vault | BE-30 | Sys/Admin |
| OQ-10 | Scheduler resolved: Supabase pg_cron | BE-31 | Sys/Admin |

**When implementation encounters an open question, Cursor must STOP and ask.** Do not guess.

---

# Cursor Build Rules Summary

1. **Implement only what this plan and SYSTEM.md specify.** Do not add features, pages, or workflows not listed.
2. **Respect phase boundaries.** Phase 1 = read-only (except drafts); Phase 2 = internal writes with approval; Phase 3 = external/scheduled.
3. **Org-scoping is mandatory.** Every data-bearing table has `org_id`; RLS enforces org scope.
4. **Use design tokens only.** No hardcoded hex/rgb in React; consume CSS variables via Tailwind.
5. **Operators are assistive.** They recommend; users confirm. No autonomous execution. Documented journeys required.
6. **RAG must cite.** Never return answers without source attribution; empty results over hallucination.
7. **Audit everything that matters.** Execution, confirmation, external calls, schedule triggers.
8. **When ambiguous, stop and ask.** Use the pause template: "This change may expand scope or maturity. Should this be treated as a separate module or later phase?"
9. **Prefer explicit over clever.** Boring, predictable code; no silent fallbacks that hide failure.
10. **No new dependencies** without explicit authorization. Use existing stack: Next.js, FastAPI, Supabase, shadcn/ui, Tailwind.
11. **Phase 0 execution order:** SA-00 → BE-00, BE-01, FE-00 (SA-00 is prerequisite for all).
12. **Brand Spec is non-negotiable for frontend.** Inter font, semantic vars (`--action`, `--bg`, etc.), Action Blue primary CTA. Do not copy token patterns from external reference without alignment.

---

# Part V — Phase 0 Reconnaissance Update (Phase 3/4 Expansion)

**Date:** Phase 3/4 expansion planning  
**Purpose:** Update implementation state before connectors, ingestion UI, role management, metrics.

---

## 5.1 Current Implementation State (Verified)

| Module | Status | Notes |
|--------|--------|-------|
| **SA-00** | **Implemented** | Supabase project, migrations folder, `.env.example`, pgvector |
| **BE-00** | **Implemented** | FastAPI, auth (JWT), org from org_context, health |
| **BE-01** | **Implemented** | Supabase migrations, naming convention |
| **BE-10** | **Implemented** | RAG retrieval, rag_sources, rag_documents, rag_chunks, rag_embeddings |
| **BE-11** | **Implemented** | workflow_defs, dry-run, list/get workflows |
| **BE-12** | **Implemented** | audit_events, audit_query function, GET /api/audit |
| **BE-20** | **Implemented** | Execute, approve/reject, approval_policies, run_approvals, workflow_runs extension |
| **BE-21** | **Partial** | Operator plan/run flow exists; no generic confirm endpoint |
| **RB-00** | **Implemented** | Org member endpoints + role constraint |
| **DC-00** | **Implemented** | Source registration + ingestion admin API |
| **DC-10** | **Implemented** | Ingestion UI under `/rag` |
| **FE-00** | **Implemented** | Next.js, globals.css tokens, shadcn, Inter |
| **FE-10** | **Implemented** | RAG query UI at `/chat` |
| **FE-11** | **Implemented** | Workflows list, dry-run UI, `/workflows` |
| **FE-12** | **Implemented** | Audit UI with filters, table, and pagination |
| **FE-20** | **Implemented** | Runs list + detail with approvals and filters |
| **FE-21** | **Implemented** | Operator console + confirm flow |
| **BE-30, BE-31, FE-30** | **Implemented** | Integrations, schedules, rollback |

---

## 5.2 Verified Endpoints (Backend)

| Endpoint | Status |
|----------|--------|
| GET /health | ✓ |
| GET /api/auth/me | ✓ |
| POST /api/rag/retrieve | ✓ |
| GET /api/workflows | ✓ |
| GET /api/workflows/:id | ✓ |
| POST /api/workflows/dry-run | ✓ |
| POST /api/workflows/execute | ✓ |
| POST /api/workflows/runs/:id/approve | ✓ |
| POST /api/workflows/runs/:id/reject | ✓ |
| GET /api/workflows/runs | ✓ |
| GET /api/workflows/runs/:id | ✓ |
| POST /api/workflows/runs/:id/rollback | ✓ |
| GET /api/workflows/:id/schedules | ✓ |
| POST /api/workflows/:id/schedules | ✓ |
| PATCH /api/workflows/schedules/:id | ✓ |
| GET /api/integrations | ✓ |
| POST /api/integrations | ✓ |
| GET /api/integrations/:id | ✓ |
| PATCH /api/integrations/:id | ✓ |
| POST /api/integrations/:id/secrets | ✓ |
| GET /api/audit | ✓ |

---

## 5.3 Verified Tables + Migrations

| Migration | Tables / Changes |
|-----------|------------------|
| 20250204000000 | pgvector, uuid-ossp |
| 20250204000001 | RLS baseline |
| 20250204000002 | organizations, organization_members |
| 20250204000003 | rag_sources, rag_documents, rag_chunks, rag_embeddings, rag_retrieval_logs, rag_search() |
| 20250204000004 | workflow_defs, workflow_runs, workflow_steps, audit_events |
| 20250204000005 | audit_query() function |
| 20250204000006 | approval_policies, run_approvals, workflow_runs extension (approval_status, required_approvals, approver_roles) |
| 20260312000003 | workflow_schedules, workflow_runs trigger_type/schedule_id/rollback_of_run_id |
| 20260314000001 | operator_links (agent handoffs) |

---

## 5.4 Drift & Gaps (Remediate Before or During Phase 3/4)

| Item | Severity | Remediation |
|------|----------|-------------|
| None | — | All known gaps resolved |

---

## 5.5 Phase 3/4 Expansion — New Modules (Implementation Order)

**Execution order (DO NOT CHANGE):**

1. Repo recon + update MASTER plan ✓
2. **RB-00** — Roles & Membership (backend + DB)
3. **IN-00** — Connector registry + secrets model
4. **IN-10** — Slack connector (approval-gated)
5. **IN-11** — Email connector (approval-gated)
6. **IN-12** — Webhook connector (approval-gated)
7. **DC-00** — Source registration + ingestion API
8. **DC-10** — Ingestion UI
9. **MT-00** — Metrics aggregation API
10. **MT-10** — Metrics UI

---

### RB-00 — Roles & Membership

| Attribute | Value |
|-----------|-------|
| **Dependencies** | BE-00 |
| **DB** | Add CHECK on organization_members.role: admin \| member (viewer optional if present) |
| **Endpoints** | GET /api/org/members, POST /api/org/members/invite (stub), PATCH /api/org/members/:id, DELETE /api/org/members/:id |
| **Auth** | Admin-only for mutate; org from auth |
| **Audit** | org.member.* |
| **Acceptance** | Admin lists/updates roles; non-admin 403 |

---

### IN-00 — Connector Registry + Secrets

| Attribute | Value |
|-----------|-------|
| **Dependencies** | BE-00 |
| **DB** | connectors (id, org_id, type, status, config, created_at, updated_at, created_by), connector_secrets (id, org_id, connector_id, key_name, encrypted_value) |
| **Encryption** | Fernet or libsodium; never return secrets to FE |
| **RLS** | org-scoped |
| **Acceptance** | Create connector config; store secrets server-side only |

---

### IN-10 — Slack Connector (Approval-gated)

| Attribute | Value |
|-----------|-------|
| **Dependencies** | IN-00, BE-20 |
| **Step type** | slack_post_message (execute-only; forbidden in dry-run; simulated in dry-run) |
| **Execute** | Real Slack API call using connector token; approval required |
| **Audit** | slack.send.requested, slack.send.sent, slack.send.failed (no message text) |
| **Acceptance** | Dry-run simulates; execute sends only after approvals |

---

### IN-11 — Email Connector (Approval-gated)

| Attribute | Value |
|-----------|-------|
| **Dependencies** | IN-00, BE-20 |
| **Provider** | SendGrid/Mailgun/SES or SMTP (document decision) |
| **Audit** | No body in logs; subject hash + recipient domain only |
| **Acceptance** | Same pattern as Slack |

---

### IN-12 — Webhook Connector (Approval-gated)

| Attribute | Value |
|-----------|-------|
| **Dependencies** | IN-00, BE-20 |
| **Config** | Allowlisted base URLs/domains; payload limits; optional HMAC |
| **Acceptance** | Dry-run simulates; execute POST after approvals |

---

### DC-00 — Source Registration + Ingestion API

| Attribute | Value |
|-----------|-------|
| **Dependencies** | BE-10, RB-00 |
| **Endpoints** | GET/POST /api/rag/sources, GET /api/rag/documents?source_id=, POST /api/rag/ingest, GET /api/rag/ingest/:id |
| **DB** | rag_ingest_jobs (optional; for async status) |
| **Auth** | Admin-only |
| **Ingestion** | Chunk JSON or pasted text; idempotency via (source_id, external_id) |
| **Acceptance** | Admin creates source; ingests doc; retrieval returns chunks |

---

### DC-10 — Ingestion UI

| Attribute | Value |
|-----------|-------|
| **Dependencies** | DC-00 |
| **Routes** | /rag/sources, /rag/ingest, /rag/documents |
| **Constraints** | Token styling; same-origin proxies; no file upload unless permitted |
| **Acceptance** | Admin creates source, ingests, sees documents; retrieval cites ingested content |

---

### MT-00 — Metrics Aggregation API

| Attribute | Value |
|-----------|-------|
| **Dependencies** | BE-12, BE-20 |
| **Endpoints** | GET /api/metrics/overview, /api/metrics/workflows, /api/metrics/rag, /api/metrics/connectors |
| **Data** | workflow execute counts, approval funnel, step failure rates, RAG latency, connector success/fail |
| **No PII** | No query text, no message bodies |
| **Acceptance** | Returns metrics <500ms; handles empty org |

---

### MT-10 — Metrics UI

| Attribute | Value |
|-----------|-------|
| **Dependencies** | MT-00 |
| **Route** | /metrics |
| **Components** | Cards, tables, simple charts (existing stack) |
| **Filters** | 7d / 30d / 90d |
| **Acceptance** | Dashboard renders; empty org handled gracefully |

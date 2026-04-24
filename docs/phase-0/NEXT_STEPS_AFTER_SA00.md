# Next Steps After SA-00 — Phase 0 Continuation

**Status:** Decision checkpoint  
**Authority:** docs/MASTER_PHASED_MODULE_PLAN.md  
**Date:** Per repository sync

---

## 1. SA-00 Status

### Complete / Incomplete
**SA-00 can be marked complete** — provided runtime validation has been performed.

### Artifact Verification (Static)
| Criterion | Status |
|-----------|--------|
| `.env.example` present with required vars | ✓ |
| `.gitignore` excludes `.env` | ✓ |
| `supabase/config.toml` present | ✓ |
| `supabase/migrations/` with pgvector + RLS baseline | ✓ |
| `docs/phase-0/SA-00_EXECUTION_PLAN.md` present | ✓ |
| No secrets in committed files | ✓ |

### Remaining Gaps (Runtime)
The following **cannot be verified** without developer execution:

1. **`supabase start` runs without error** — Requires Docker + Supabase CLI
2. **`supabase db reset` applies migrations** — Requires local Supabase running
3. **`SELECT * FROM pg_extension WHERE extname = 'vector'` returns one row** — Requires DB connection

### Corrective Action if Gaps Exist
- If Supabase CLI or Docker is not installed: follow Step 1–2 of SA-00_EXECUTION_PLAN.md
- If `supabase start` fails: check Docker, port conflicts (54321–54324, 54322)
- If migrations fail: verify migration SQL syntax; check Supabase/Postgres version compatibility

### OQ Blockers for SA-00
**None.** No Open Questions block SA-00.

---

## 2. Recommended Next Module

### Module ID
**BE-00 — Foundation & Auth Baseline**

### Why It Must Come Next
1. **Dependency chain:** All Phase 1 backend (BE-10, BE-11, BE-12) depends on BE-00 for auth, org context, and Supabase connection.
2. **Frontend dependency:** FE-00 can run in parallel (placeholder needs no API), but FE-10+ requires `GET /api/auth/me` and RAG/audit endpoints — all behind BE-00.
3. **BE-01 overlap:** Migration tooling and folder conventions are already satisfied by SA-00. BE-01 adds convention documentation; it is not a blocking dependency.
4. **FE-00 parallel:** FE-00 can proceed without BE-00 for a minimal placeholder, but BE-00 is the critical path for unlocking Phase 1.

### What It Unlocks
- Auth contract for all subsequent modules
- Org-scoped access primitives (foundation for RLS)
- FastAPI skeleton for BE-10, BE-11, BE-12
- `/health` and `/api/auth/me` endpoints required by frontend

---

## 3. Open Question Triage Table

| OQ ID | Question | Status | Owner | Risk if Deferred |
|-------|----------|--------|-------|------------------|
| **OQ-1** | Org model: Supabase Organizations vs custom tables | **Now** | Product / Platform | BE-00 cannot create `organizations` / `organization_members` or implement org-scoped RLS. Auth middleware cannot attach org to context. |
| **OQ-2** | Auth provider: email/password, magic link, or both | **Now** | Product | BE-00 Stop condition: "Auth provider choices — document and proceed with one." Incomplete docs block auth implementation. |
| OQ-3 | Workflow definition schema | Defer | Backend | Blocks BE-11 only (Phase 1). |
| OQ-4 | Dry-run semantics | Defer | Backend | Blocks BE-11 only. |
| OQ-5 | Audit event schema | Defer | Backend | Blocks BE-12 only. |
| OQ-6 | Token JSON: Figma exports vs minimal globals.css | Defer | Frontend | FE-00 can proceed with minimal tokens in globals.css per plan mitigation. |
| OQ-7 | Phase 2 operator types | Defer | Product | Phase 2 only. |
| OQ-8 | Journey doc format | Defer | Backend | Phase 2 only. |
| OQ-9 | Credential encryption | Defer | Sys/Admin | Phase 3 (BE-30) only. |
| OQ-10 | Scheduler choice | Defer | Sys/Admin | Phase 3 (BE-31) only. |

### Summary
- **Must resolve now:** OQ-1, OQ-2
- **Can defer:** OQ-3 through OQ-10

---

## 4. Next Module Execution Boundary — BE-00

### Exact Scope

**Included:**
- FastAPI app entrypoint (`app/main.py` or equivalent)
- Config loading (pydantic-settings, env vars from SA-00)
- Supabase client initialization
- Auth middleware: validate JWT, attach `user_id` to request context
- Org context: attach `org_id` to request context (per OQ-1 resolution)
- `GET /health` — no auth
- `GET /api/auth/me` — requires auth; returns `{ user_id, org_id?, email? }`
- Structured logging (request_id, user_id, org_id, status_code, duration_ms)
- CORS allowing `http://localhost:3000`, `https://localhost:3000`
- Supabase migrations for `organizations`, `organization_members` (if OQ-1 = custom)

**Excluded:**
- User registration UI
- Org creation UI
- RLS policy implementation for Phase 1 tables (BE-10, BE-11, BE-12)
- Audit event persistence

### Role
**Backend** (Principal Backend Engineer)

### Files / Directories
- `backend/` or `api/` (or project-conventional root for FastAPI)
- `app/main.py`, `app/config.py`, `app/auth/`, `app/core/logging.py`
- `supabase/migrations/` — new migration(s) for org tables if custom model
- `requirements.txt` or `pyproject.toml`
- No frontend files; no Phase 1 feature code

### Dependencies
- **Internal:** SA-00 (complete)
- **External:** FastAPI, Supabase Python client, python-dotenv, pydantic-settings

### Acceptance Criteria
- [ ] `GET /health` returns 200 without auth
- [ ] `GET /api/auth/me` returns 401 without valid JWT
- [ ] `GET /api/auth/me` returns `{ user_id, org_id?, email? }` with valid JWT
- [ ] Logs include request_id, user_id, org_id (when present), status_code, duration_ms
- [ ] CORS allows Next.js dev origin(s)

### Stop Conditions
- **OQ-1 unresolved:** Cannot create org tables or attach org_id to context. STOP.
- **OQ-2 unresolved:** Auth provider not documented. STOP.
- Org model undefined (Supabase Organizations vs custom)
- Auth provider choices not documented

### Pre-Execution Checklist
1. [ ] OQ-1 resolved: Org model decision documented
2. [ ] OQ-2 resolved: Auth provider decision documented
3. [ ] SA-00 runtime validation complete (`supabase start`, migrations applied)
4. [ ] `.env` populated with SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
5. [ ] Python 3.10+ and venv available

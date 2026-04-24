# Open Question Resolutions (Phase 0 / BE-00)

**Authority:** Decisions recorded here unblock BE-00 per docs/MASTER_PHASED_MODULE_PLAN.md and docs/phase-0/NEXT_STEPS_AFTER_SA00.md.

---

## OQ-1: Org / Tenant Model

**Resolution:** Option A — **Single-Org-per-User (custom tables)**

- Use custom `organizations` and `organization_members` tables.
- Each user has at most one org (no multi-org switching).
- Migrations for these tables are in scope for BE-00.
- RLS and org context use: lookup `org_id` from `organization_members` where `user_id = auth.uid()` (single row per user).

---

## OQ-2: Auth Provider

**Resolution:** Option A — **Supabase Auth (email + magic link; email confirmation required)**

- **Methods:** Email + password and magic link (passwordless).
- **Email confirmation:** Required before first sign-in.
- Supabase Auth is the sole provider; no additional OAuth providers unless added later.
- BE-00 auth middleware validates Supabase-issued JWTs; no custom claims required for baseline (org from DB lookup).

---

## BE-00 Status

With OQ-1 and OQ-2 resolved, **BE-00 execution is unblocked** subject to:
- SA-00 runtime verification complete
- `.env` populated with Supabase URL and keys

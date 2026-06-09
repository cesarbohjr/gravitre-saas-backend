# Gravitre AI / Agents / Training Fix Report

**Date:** 2026-06-09  
**Engineer:** Production fix pass (Cursor)

## 1. Root causes found

| Issue | Root cause |
|-------|------------|
| **AI chat — “Could not start a new conversation”** | `conversationsApi.create` failed when org context was missing or stale (demo org in storage, no membership). Generic toast hid backend `403` detail. |
| **Training Hub error banner** | SWR fetched `/api/training/*` before org was resolved; backend returned `403 Organization context required` when membership/org header was absent. |
| **Audit log load failure** (screenshot) | Same org-context pattern via FastAPI `/api/audit` rewrite — not missing route, missing membership. |
| **Agents flash then 2 agents** | `apps/web/app/api/agents/route.ts` injected **2 demo agents** when DB list was empty; page used **5 hardcoded fallback agents** in SWR + `normalizeAgentsResponse`. |
| **New agents not in list** | No SWR cache invalidation after create; demo fallback masked real empty responses. |
| **require_admin blocked owners** | Backend only accepted `role == "admin"`, not `owner`. |
| **Master admin** | No platform-level admin table; user needed idempotent `owner` membership + platform registry. |

## 2. Files changed

### Frontend (`apps/web`)
- `app/api/agents/route.ts` — removed demo bootstrap/fallback; returns real DB agents only
- `app/agents/page.tsx` — removed mock agents; SWR revalidate; empty/error states; collapsible detail panel + `localStorage`
- `app/agents/new/page.tsx` — `mutate("/api/agents")` after create
- `app/assistant/page.tsx` — `ensureSelectedOrg` before conversation create; `parseChatError` toasts
- `app/training/page.tsx` — org gate before fetch; clearer errors, retry, empty state
- `lib/supabase/server.ts` — `resolveOrgId` no longer falls back to demo org for authenticated users

### Backend
- `app/auth/platform_admin.py` — new platform admin helpers
- `app/auth/dependencies.py` — platform admin org override; `owner` accepted as admin

### Supabase
- `supabase/migrations/20260609190000_platform_admin_cesar.sql`

### Tests
- `backend/tests/auth/test_platform_admin.py`

## 3. Supabase / RLS changes

- Added **`platform_admins`** table (RLS enabled, **no policies** → only service role manages rows; does not weaken tenant RLS).
- Idempotent seed grants **`cesar.bohorquez.jr@gmail.com`**:
  - row in `platform_admins`
  - `organization_members.role = owner` for Acme Corp (`00000000-0000-0000-0000-000000000001`)
  - sync `users.role = owner` when `auth.users` row exists
- **No global RLS disable.** Existing org-scoped policies unchanged.

## 4. Master admin — cesar.bohorquez.jr@gmail.com

Migration `20260609190000_platform_admin_cesar.sql`:

1. Looks up `auth.users.id` by email (no-op notice if user not signed up yet).
2. Upserts `platform_admins`.
3. Upserts `organization_members` as **owner** for Acme Corp.
4. Updates/inserts `users` profile row as **owner**.

Backend treats platform admins as org admins and honors `x-org-id` for cross-org operations without bypassing RLS for other tenants’ data reads (service role still scoped by org_id in queries).

**Verification SQL:**

```sql
SELECT pa.email, pa.user_id, om.org_id, om.role, u.role AS users_role
FROM platform_admins pa
LEFT JOIN organization_members om ON om.user_id = pa.user_id
LEFT JOIN users u ON u.auth_user_id = pa.user_id
WHERE lower(pa.email) = lower('cesar.bohorquez.jr@gmail.com');
```

## 5. Verification steps

1. **Apply migration:** `supabase db push` (or run migration in Supabase SQL editor).
2. **Sign in** as `cesar.bohorquez.jr@gmail.com` on https://gravitre.app
3. **Assistant:** New chat → should create conversation (no generic error).
4. **Training:** `/training` → no red banner when org resolved; empty state if no data.
5. **Agents:** `/agents` → all real agents; create agent → appears immediately; toggle panel hide/show persists.
6. **Audit:** `/audit` → loads when org membership present.
7. **Backend tests:** `cd backend && python -m pytest tests/auth/test_platform_admin.py -q`
8. **Typecheck:** `cd apps/web && pnpm exec tsc --noEmit`

## 6. Remaining risks

- Migration is no-op until the user exists in `auth.users` (first login required once).
- Platform admin table is service-role only; UI does not yet expose a “platform admin” badge.
- Workflow status toast (“Unable to update workflow status”) is a separate workflows API issue — not in this pass.
- Audit/training still require valid org membership for non–platform-admin users.
- `FASTAPI_BASE_URL` and AI provider keys must remain set on Vercel/Railway for streaming chat.

## 7. Manual QA checklist

- [ ] Login as cesar.bohorquez.jr@gmail.com
- [ ] Run verification SQL — `owner` + `platform_admins` row
- [ ] Assistant: start new conversation, send message in Fast/Standard/Reasoning modes
- [ ] Training: page loads without error; create dataset (optional)
- [ ] Agents: list matches Supabase `agents` for org; no demo-only pair after refresh
- [ ] Agents: create via `/agents/new` — appears in grid without hard refresh
- [ ] Agents: collapse detail panel — grid expands; preference survives reload
- [ ] Audit: logs load or show empty state (not error skeleton)
- [ ] Second org user still cannot read another org’s agents (RLS spot check)

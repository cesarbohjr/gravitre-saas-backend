# Settings → Webhooks: real data only (2026-07-19)

## Fix

- Removed hardcoded fake Slack/Zapier webhook rows from `WebhooksSettings`.
- UI now loads/creates/deletes via `/api/settings/webhooks` (org-scoped Supabase `webhooks` table).
- Empty org shows genuine empty state: **No webhooks configured yet**.

## Demo bootstrap audit

`ensureDemoDataForOrg` (`apps/web/lib/supabase/demo-bootstrap.ts`) **no-ops** unless `orgId` is exactly one of:

- `00000000-0000-0000-0000-000000000001` (Acme Corp)
- `11111111-1111-4111-8111-111111111111` (Gravitre Labs)

Real customer orgs (including Cesar’s workspace) cannot receive demo webhook seeds through that path.

## FASTAPI_BASE_URL / demo-runtime-store (same class as 0.1)

**Before:** Approvals, operator sessions, and training Next routes fell back to in-memory `demo-runtime-store` whenever `FASTAPI_BASE_URL` was unset — reachable by any caller, including real orgs under misconfiguration.

**After:** Fallback only when `ALLOW_DEMO_RUNTIME_FALLBACK=1` and `VERCEL_ENV !== production`. Otherwise **503** with empty/honest error — never fabricated rows.

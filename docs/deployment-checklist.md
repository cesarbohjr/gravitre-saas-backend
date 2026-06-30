# Gravitre Deployment Checklist

## Before Every Deploy

### Backend (Railway)
- [ ] All env vars set (see `backend/.env.example`)
- [ ] `TAVILY_API_KEY` set for assistant web search (`npm run tavily:fill-env` or Railway Variables)
- [ ] `DISABLE_AI=false` (unless intentional)
- [ ] `AI_HARD_BUDGET_ENABLED=true` for production
- [ ] Supabase migrations applied: `supabase db push`
- [ ] pytest passes: `cd backend && pytest`
- [ ] Health check responds: `GET /health` → 200

### Frontend (Vercel)
- [ ] `FASTAPI_BASE_URL` points to live Railway backend
- [ ] `NEXT_PUBLIC_SUPABASE_URL` set
- [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY` set
- [ ] `pnpm build` passes with no type errors
- [ ] ESLint clean

### Stripe (when billing changes are deployed)
- [ ] `STRIPE_METER_EVENT_NAME` matches live meter
- [ ] `STRIPE_METERED_PRICE_*` IDs are live (not test)
- [ ] Webhook secret updated if rotated
- [ ] Keys rotated if exposed in any log or chat

### Database
- [ ] `supabase db push` run against production project
- [ ] All migrations confirmed applied
- [ ] RLS enabled on all tenant tables

### After Deploy
- [ ] Run: `bash scripts/test-integration.sh` (or on Windows: `$env:BACKEND_URL="https://your-backend.up.railway.app"; .\scripts\test-integration.ps1`)
- [ ] Open `/assistant` and send a test message
- [ ] Ask an external question (e.g. current industry news) — web search chip should be green or amber, not falsely green on error
- [ ] Ask "what is Gravitre" — answer should cite platform knowledge (run `npm run rag:seed-platform` once if empty)
- [ ] Open `/operator` and verify command input renders
- [ ] Check Railway logs for any startup errors
- [ ] Check Vercel function logs for any proxy errors

### Billing Go-Live

- [ ] Run dry-run first:
      `POST /api/admin/billing/attach-all-metered-prices`
      Body: `{"dry_run": true}`
      Review output — confirm plan codes and subscription IDs look correct

- [ ] Run live attachment for one org first:
      `POST /api/admin/billing/attach-metered-price`
      Body: `{"org_id": "<internal-org-id>", "dry_run": false}`
      Verify in Stripe Dashboard that the subscription now shows two line items

- [ ] Confirm next invoice preview shows metered item:
      Stripe Dashboard → Customer → Subscription → Upcoming invoice → should show metered usage

- [ ] Run bulk attachment for all orgs:
      `POST /api/admin/billing/attach-all-metered-prices`
      Body: `{"dry_run": false}`

- [ ] Monitor for 24 hours:
      Check Stripe Dashboard → Billing → Meters
      Confirm `ai_credits_used` events are accumulating
      Confirm no unexpected charges triggered

### Billing Verification
- [ ] GitHub secret `BACKEND_URL` set for CI integration smoke test
- [ ] GitHub secret `INTERNAL_API_SECRET` set (matches Railway `INTERNAL_API_SECRET`)
- [ ] `usage-sync.yml` workflow enabled in GitHub Actions
- [ ] `knowledge-sync.yml` workflow enabled (hourly `POST /api/internal/knowledge/sync-due`)
- [ ] First manual sync: Actions → Usage Sync → Run workflow → verify Railway logs
- [ ] First manual knowledge sync: Actions → Knowledge Sync → Run workflow → HTTP 200
- [ ] Stripe Dashboard → Billing → Meters → confirm `ai_credits_used` events appear

### CI Integration
- [ ] GitHub secret `BACKEND_URL` set for CI
- [ ] Integration smoke test job passing on push to main

## Environment Variable Reference
See `backend/.env.example` and `apps/web/.env.example`
for the full list with descriptions.

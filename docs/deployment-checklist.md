# Gravitre Deployment Checklist

## Before Every Deploy

### Backend (Railway)
- [ ] All env vars set (see `backend/.env.example`)
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
- [ ] Open `/operator` and verify command input renders
- [ ] Check Railway logs for any startup errors
- [ ] Check Vercel function logs for any proxy errors

## Environment Variable Reference
See `backend/.env.example` and `apps/web/.env.example`
for the full list with descriptions.

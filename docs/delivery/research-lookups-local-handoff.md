# Local handoff — Research Lookups + Internet Research go-live

**Use this doc when continuing on your machine** (tokens in `backend/.env.operator.local`).

Cloud agent completed steps 2–3. Migration + live verification remain.

---

## Already done (cloud @ 2026-07-18T16:45:34Z)

| Step | Status | Evidence |
|------|--------|----------|
| Stripe meter + $0.35 price | **PASS** | `mtr_61V3zJsvqi21Hijog41GkcGZTLqrPXdA`, `price_1TubMWGkcGZTLqrPwxDBmEDA` |
| Railway env vars | **PASS** | `STRIPE_RESEARCH_LOOKUP_METER_EVENT_NAME`, `STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID` on `gravitre-saas-backend` |

Tracker: `docs/delivery/research-lookups-go-live-status.json`

**Do not re-run Stripe seed unless you need a new price.**

---

## Local prerequisites

1. Pull latest `main`:
   ```bash
   git pull origin main
   ```

2. Confirm `backend/.env.operator.local` has (at minimum):
   - `SUPABASE_ACCESS_TOKEN` (or run `supabase login`)
   - `SUPABASE_DB_PASSWORD` (if link prompts)
   - `RAILWAY_TOKEN` or `railway login`
   - `STRIPE_SECRET_KEY`
   - `API_PUBLIC_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OAUTH_SMOKE_ORG_ID` (for live smokes)

3. Optional: `SUPABASE_PROJECT_REF=smyeexlrqdpymwjmgzqu` (prod ref in repo docs)

---

## Step 1 — Apply Supabase migrations (prod)

Applies all pending migrations, including:

- `20260718120000_internet_research_metering.sql`
- `20260718130000_internet_research_circuit_breaker.sql`
- `20260719120000_billing_plans_research_lookups.sql`

### Option A — one script (loads `.env.operator.local`)

```bash
npm run billing:research-lookups-go-live
```

Stripe/Railway steps will no-op or show PASS if already set; migration is the important part.

### Option B — manual Supabase CLI

```bash
supabase login   # if no SUPABASE_ACCESS_TOKEN
supabase link --project-ref smyeexlrqdpymwjmgzqu --yes
supabase db push
supabase db query --linked -f supabase/scripts/verify_research_lookups_billing.sql
```

### Option C — PowerShell query helper (Windows)

```powershell
.\scripts\supabase-db-query.ps1 -RepairLink -File supabase\scripts\verify_research_lookups_billing.sql
```

**Expected verify output:** `research_lookups_per_month` = 10 / 60 / 200 on node/control/command; `research_lookup` overage = 0.35; `usage_records.stripe_reported_at` column exists.

Update status JSON step `1_migration_prod_staging` → `PASS` with timestamp after success.

---

## Step 2 — Redeploy backend (Railway)

Railway vars are set; trigger redeploy so the service picks them up:

```bash
# if linked
railway up --service gravitre-saas-backend

# or redeploy from Railway dashboard
```

Confirm health: `curl https://gravitre-saas-backend-production.up.railway.app/health`

---

## Step 3 — Live verification (before any flags)

**Do not flip `INTERNET_RESEARCH_ENABLED` or `NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED` yet.**

Run in order; each must PASS with live evidence (audit/trace), not pytest alone.

```bash
# 1) Four canonical checks
python scripts/smoke-milestone1-live-reverify.py

# 2) Internet research E2E (one trace)
python scripts/smoke-internet-research-live.py --json docs/delivery/internet-research-live-latest.json

# 3) Confirm stop-early live (same milestone script, internal probe)
python scripts/smoke-milestone1-live-reverify.py
```

Record results in `docs/delivery/internet-research-pre-go-live-verification.json` (append sections per Linear ticket rules).

---

## Step 4 — Go live (same release)

Only after step 3 PASS:

| Platform | Variable | Value |
|----------|----------|-------|
| Railway | `INTERNET_RESEARCH_ENABLED` | `true` |
| Vercel | `NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED` | `true` |

Flip **both in the same release**, then redeploy backend + frontend.

```bash
railway variable set INTERNET_RESEARCH_ENABLED=true --service gravitre-saas-backend
# Vercel: dashboard or vercel env pull/push for NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED
```

**Optional after flags on:** attach research lookup metered price to test org first, then bulk:

```http
POST /api/admin/billing/attach-metered-price
{"org_id": "<smoke-org>", "dry_run": false}
```

Use a dedicated admin endpoint for research lookup attachment if added; today AI-credits attach is `attach-metered-price` — confirm research lookup attach path in `billing_sync.py` before prod bulk attach.

---

## Step 5 — Deferred (later)

Outputs/Mesons automatic Stripe billing parity — pre-existing gap; see `docs/delivery/outputs-meson-billing-mechanism-audit.json`.

---

## Cursor local prompt (paste into new Agent chat)

```
Continue research lookups + internet research go-live from docs/delivery/research-lookups-local-handoff.md.

Done already: Stripe meter price_1TubMWGkcGZTLqrPwxDBmEDA + Railway STRIPE_RESEARCH_LOOKUP_* vars.

Run locally in order:
1. supabase db push + verify_research_lookups_billing.sql
2. Railway redeploy
3. smoke-milestone1-live-reverify.py + smoke-internet-research-live.py (live PASS evidence)
4. Only if step 3 PASS: flip INTERNET_RESEARCH_ENABLED + NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED together

Do NOT attach metered price to prod subs or flip public flags until step 3 PASS.
Tokens are in backend/.env.operator.local.
```

---

## Rollback

```bash
railway variable set INTERNET_RESEARCH_ENABLED=false --service gravitre-saas-backend
# Vercel: NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED=false
```

Immediate off-switch; no migration rollback required for flags.

# Stripe — Research Lookups metered billing (human action required)

**Status:** Spec ready — **do not paste placeholder Price IDs into Railway.**

Research Lookups overage uses a **separate** Billing Meter from `ai_credits_used`.

## CLI alternative (preferred when `STRIPE_SECRET_KEY` is set)

**Staging first (`sk_test_*` only):**

```bash
export STRIPE_SECRET_KEY=sk_test_...
npm run billing:stripe-research-lookup-meter:staging
```

Pull test key from Railway and push Price ID back (requires `railway login` or `RAILWAY_TOKEN`):

```bash
bash scripts/stripe-seed-research-lookup-staging.sh --from-railway --push-railway
```

Generic (test or live key):

```bash
export STRIPE_SECRET_KEY=sk_test_...   # staging first; sk_live_... for prod after live PASS
python backend/scripts/stripe_seed_research_lookup_meter.py
```

Or run the full ordered prep (migration + Stripe + Railway hints):

```bash
bash scripts/apply-research-lookups-billing-go-live.sh
```

Requires `SUPABASE_ACCESS_TOKEN` (or `supabase login`) for `db push`, and `railway login` to auto-set Railway vars.

## Dashboard steps (manual fallback)

1. **Billing → Meters → Create meter**
   - Event name: `research_lookups_used`
   - Aggregation: Sum
   - Value settings: Integer

2. **Products → Create product** (or reuse a “Gravitre usage overage” product)
   - Name: `Research Lookup Overage`
   - Description: Pay-as-you-go live internet research lookups above plan allotment ($0.35/lookup)

3. **Prices → Add price**
   - Pricing model: Usage-based, metered
   - Meter: `research_lookups_used`
   - Unit price: **$0.35 USD** per unit
   - Billing period: Monthly (matches subscription cycle)

4. **Optional — attach to subscriptions**
   - Add the metered price as a second subscription item (same pattern as `STRIPE_METERED_PRICE_ID_*` for AI credits)
   - Or include at checkout when Research Lookups goes live

## Railway env (after creation)

```bash
STRIPE_RESEARCH_LOOKUP_METER_EVENT_NAME=research_lookups_used
STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID=price_xxxxxxxx
```

## Code path (already wired when env set)

- `backend/app/billing/stripe_research_lookup_metering.py` — reports **overage lookups only** from `usage_records` where `metric_type=research_lookups` and `stripe_reported_at IS NULL`
- Hourly sync via `usage_scheduler` + `POST /api/internal/billing/sync-usage`

## Test-mode verification (before prod)

1. Set test-mode Price ID in staging Railway
2. Attach metered price to a test subscription
3. Insert or trigger research lookup usage above included allotment
4. Run sync-usage (dry_run=false)
5. Confirm Stripe test invoice / meter event at **$0.35 × overage count**

## Customer visibility gate

Per sequencing decision **(a)**: do **not** attach live metered price to production subscriptions or publish pricing copy until `INTERNET_RESEARCH_ENABLED=true` and live verification PASS.

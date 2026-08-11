# Meson scaffolding addons — archived (honesty close)

**Date:** 2026-08-09  
**Decision:** Remove entirely from customer-facing UI; archive catalog rows (no “coming soon” placeholder).

## Defect

| SKU | Seeded price | Origin |
|---|---|---|
| Multi-language | $79/mo | `20260428011000_monetization_access_control.sql` (2026-04-28 `05d5a649`) |
| Advanced Analytics | $99/mo | same |
| Compliance Pack | $199/mo | same |
| Custom Model Training | $299/mo | same |

Never product-authorized, never Stripe-wired (`stripe_price_id` null), never gated (`require_addon` unused for these codes). Live on Settings → Meson Addons with Enable toggles.

## Fix

1. Migration `20260809044816_archive_scaffolding_meson_addons.sql` — `archived_at`, rename, price→0; clear inert JSON flags.
2. `GET /api/settings/meson-addons` returns **only** rows with `stripe_price_id` set and `archived_at` null.
3. `monthly_total_usd` sums only those billable rows.
4. Settings UI: no scaffolding cards; empty state “No billable Meson addons”; Voice plan-included card remains.

## Phase 3 — same-era audit

| Artifact | Finding |
|---|---|
| `meson_addon_catalog` (this migration) | **Only** fictitious priced SKUs were the five seeds (4 + voice). Voice already retired; four archived here. |
| Adjacent Apr 2026 migrations (`billing_events_demo`, SSO, training entities, etc.) | **No** other customer-facing priced catalog seeds of the same shape found. |
| `billing_plans` seeds | Real platform plans (Node/Control/Command) — different class; not scaffolding Meson SKUs. |

## Verification (deploy tip `34006e15`)

| Check | Result |
|---|---|
| API tip | **PASS** — `GET /health` `git_sha=34006e15136390ad8ccded0f0e2292a5e3f160f1` |
| Railway | **PASS** — SUCCESS deploy at tip |
| Vercel | **PASS** — production READY `dpl_8EusyKUHeGGBy6hkbrnocshN5agV` on `34006e15` |
| `GET /api/settings/meson-addons` | **PASS** — `addons=[]`, `monthly_total_usd=0`, `addon_audit.scaffolding_skus=archived_hidden` @ `2026-08-09T06:52:32Z` |
| Catalog archived | **PASS** — all five codes `archived_at` set, price `$0` |
| Orgs with scaffolding flags | **PASS** — `0` |
| Unit | **PASS** — `test_meson_addon_catalog_honesty.py` 4 passed |
| Evidence JSON | `docs/delivery/meson-scaffolding-addons-archived-live.json` |

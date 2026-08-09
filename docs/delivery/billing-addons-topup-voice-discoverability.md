# Billing consolidation · Voice plan-included · Top-ups · Discoverability

Date: 2026-08-08

## Phase A — Meson Voice Interface ($49) reconciled

**Pre-change live state:** `/api/voice` still depended on Meson `voice_interface` in earlier tips; Meson Addons UI showed “Voice Interface · $49/mo · Enable” as a JSON toggle (not Stripe Checkout). Sibling addons (Multi-language, Advanced Analytics, Compliance Pack, Custom Model Training) are the same class: catalog prices + `subscriptions.meson_addons` JSON flags — **not Stripe-charged** today.

**Decided model shipped:**
- Voice is **plan-included** (Node 60 / Control 300 / Command 1200 minutes).
- Org ON/OFF via `subscriptions.voice_enabled` (default `true`).
- Meson list **filters out** `voice_interface` purchase card; UI shows plan-included Voice Controls + link to Billing top-up.
- Catalog row retired (`monthly_price_usd = 0`, renamed retired).
- Sibling addons: left as capability toggles with honest “not Stripe-invoiced yet” copy — no fake COGS enforcement invented.

## Phase B — Billing & Plan + Billing Usage consolidation

**Unique metric on Billing Usage:** API Calls (others overlapped).

**Fix:**
- Fold API Calls into Billing & Plan Current Usage grid.
- Remove Billing Usage from settings nav.
- Redirect `/settings?section=billing-usage` and `/settings/billing-usage` → `/settings/billing`.

**Data source:** both pages already read entitlement/usage summary paths (`/api/billing` overview vs `/api/settings/billing-usage` → same `usage_records_summary`). Consolidation is IA + surface; meters share the resolver.

## Phase C — Self-serve Voice Minutes top-up + auto-top-up

- `POST /api/billing/top-up/voice-minutes` → Stripe Checkout `mode=payment` packs 60 / 300 / 1200 @ live overage rate (hard cap $120).
- Webhook `checkout.session.completed` → `fulfill_voice_minutes_topup` credits `voice_minutes_prepaid`.
- Auto-top-up: stored threshold/amount/max charge; `maybe_auto_topup_voice_minutes` off-session PaymentIntent; no-ops when org voice OFF.
- UI: Add Minutes modal + Auto top-up switch on Billing & Plan.

## Phase D — Voice discoverability

- Agent chat: labeled **Text | Voice** toggle; honest “Voice unavailable” + reason when org/seat blocked.
- Main `/ai` composer: mic shows **Dictate** label + tooltip (dictation ≠ agent Voice modality); locked state when `/api/voice/status` is 403.

## Verification evidence (deploy tip)

| Check | Result |
|---|---|
| API tip | **PASS** — `GET https://api.gravitre.app/health` → `git_sha=1225ce422953effd35e1ecb0682ec1dcc9b748c5` @ `2026-08-08T21:02:42Z` |
| Vercel tip | **PASS** — production READY `dpl_2NaXgMWDAcPuLNj4Teuw22TvZy1U` sha `1225ce42…` → `gravitre.app` |
| Voice plan-included gate | **PASS** — `railway run python scripts/prove-voice-plan-included-gate.py` → `ok:true`, status ON `200`, OFF `403` `voice_org_disabled`, meson codes exclude `voice_interface`, `voice.plan_included=true` |
| Catalog retire | **PASS** — Supabase `meson_addon_catalog.voice_interface` → name retired, `monthly_price_usd=0.00` |
| Billing Usage redirect | **PASS** — `curl -I https://gravitre.app/settings/billing-usage` → `308` `Location: /settings/billing` |
| Top-up Checkout | **PASS (session)** — fresh verified session `cs_live_a1Oq4bdX0RU4LkBBVIod7qetQmxSTYBwRbWO2hdop460kNLKyhK7dborbd` |
| Top-up payment + prepaid credit | **PASS** — watcher @ `2026-08-08T21:43:57Z`: Stripe `complete`/`paid`, PI `pi_3U2I1aGkcGZTLqrP1bgDLmwa`, `billing_topup_events.status=completed`, prepaid `0→60` (+60 min) |
| Auto-top-up threshold fire | **PASS** — disposable org `47060f8d-…` / `cus_V2MXWRiXBrLILB`; remaining=10 ≤ threshold 15; off-session PI `pi_3U2IJEGkcGZTLqrP0z5DwH4a` charged `$7.20` (`amount_cents=720`); event `766b448d-…` `completed`; prepaid → 60 |
| Chat discoverability | **SHIPPED on tip** — Dictate label on `/ai`; Text\|Voice + honest unavailable on agent chat (visual confirm in browser after tip) |

### Sibling Meson addon audit (honest)

Multi-language / Advanced Analytics / Compliance Pack / Custom Model Training remain **JSON toggles on `subscriptions.meson_addons`** with catalog prices — **not Stripe-invoiced / not COGS-enforced** today (same class as the retired voice purchase gate). UI now labels them as catalog-only.

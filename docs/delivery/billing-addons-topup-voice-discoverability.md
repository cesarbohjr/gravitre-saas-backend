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

## Verification checklist (deploy tip)

- [ ] `GET https://api.gravitre.app/health` → `git_sha` matches this tip
- [ ] `python scripts/prove-voice-plan-included-gate.py` → ok
- [ ] Meson Addons: no $49 Voice Interface Enable card
- [ ] Billing Usage nav gone; old route redirects
- [ ] Manual top-up Checkout + prepaid minutes + Stripe charge
- [ ] Auto-top-up fires in disposable org below threshold
- [ ] Chat: Dictate label on `/ai`; Text|Voice on agent chat

# Post-v0 regression — billing / top-up / voice discoverability polish

Date: 2026-08-09  
Visual tip merged to `main`: `91f5aa13`  
API tip at verify time: `1225ce42` (Railway may SKIP web-only deploys)

## Scope check

`cf27ed38..91f5aa13` is presentation + capture harness only:

- Billing Current Usage (metered API Calls chip, auto-top-up copy, Add Minutes modal)
- VoiceModeToggle (`aria-disabled` + reachable tooltip)
- Agent chat `showLabel` on Dictate
- e2e billing-states shot + fixtures + PNGs

No `/api/*` routes, migrations, entitlement gates, or Stripe math in polish commits.

## Regression gate (live)

| # | Check | Result |
|---|---|---|
| 1 | Meson Addons: no `$49` voice purchase card | **PASS** — `railway run python scripts/prove-voice-plan-included-gate.py` → `ok:true`; meson codes = multi_language, advanced_analytics, compliance_pack, custom_model_training only; `voice.plan_included=true` |
| 2 | `/settings/billing-usage` → Billing & Plan | **PASS** — `curl -I https://gravitre.app/settings/billing-usage` → `308` `Location: /settings/billing` |
| 3 | Add Minutes creates resolvable Checkout URL | **PASS** — `prove-voice-topup-checkout.py` → `200`, session `cs_live_a1kRh2hn8BuHniTZgEZrQ5dy37uOHIyjUvDgTmWzssOvbALJX6aHrm8jBs`, amount `$7.20`; browser load shows **Voice Minutes top-up (60 min)** / Gravitre AI (not “Something went wrong”) |
| 4 | Voice org ON/OFF still 200/403 | **PASS** — same prove script: ON `200`, OFF `403` `voice_org_disabled` |

## Phase C close (already recorded)

See `billing-addons-topup-voice-discoverability.md`:

- Manual top-up PI `pi_3U2I1aGkcGZTLqrP1bgDLmwa` succeeded; prepaid 0→60
- Auto-top-up PI `pi_3U2IJEGkcGZTLqrP0z5DwH4a` succeeded on disposable org; cleaned up

## Open (product, not polish)

Presence strip amber `billing` state in agent chat remains unwired — no TTS playback / 402 path on that surface yet. Left unwired rather than faking a trigger.

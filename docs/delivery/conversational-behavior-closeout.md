# Conversational behavior — closeout (2026-08-12)

## Phase 0 (honest)

LIVE department agents used Module D register/tone + honesty rules, but **no real conversational-structure layer**. Classical `RULES_SECTION` / MARKETING persona are **not** injected into LIVE. Strongest gap: don’t-over-answer. See `conversational-behavior-phase0-audit.md` + prompt dump.

## Phase 1–2

- Shared `## Conversational behavior` in `backend/app/services/conversational_behavior.py`
- Wired into LIVE (`build_module_d_unified_system_prompt`) and classical (`_build_system_prompt`)
- Composes alongside Module D registers + Voice; honesty boundary preserved
- Prompt 3 dialogue library (`voice_expression_range`) unchanged — third composable layer

## Phase 3 — before / after (Marketing Analyst)

| Turn | Before (`1a7623b5…`, conv `99a96c5f-abe2-4085-9ce0-3cc8053c7e23`) | After (`041c91a7…`, conv `84ccb0e4-f765-4ad7-ba53-e6f86ffdeb35`) |
| -- | -- | -- |
| 1 `help me improve our SEO` | 132-word SEO document, **no** clarifying Q | Clarifying choice: organic / ranking drop / content plan + site |
| 2 scope follow-up | Defined “organic traffic”, soft ask | Continues thread + clarifying goal |
| 3 blog vs product | Product first + research dump (92w) | Product first, shorter |
| 4 two fixes only | 108w Shopify research pad | Budget-respecting short sketch |
| 5 remind decision | **Denied** prior decision | Restated product-pages-first |

**Sales Agent** (second department, platform-wide): clarify + short + prior recall + length variation — `pass=true` on tip `041c91a7`.

## Deploy evidence

- Feature tip (rules 1–5 ship): `041c91a783129e8bf3af6a5562b8d302c941e777`
- After probe: `conversational-behavior-after-transcript.json` — `verdict=PASS` for Marketing Analyst + Sales Agent
- Before baseline: `conversational-behavior-before-transcript.json` — `verdict=FAIL` (rescored)
- Wave 2 (rules 6–10) tip: `57cccaf16cb518a8a2e36b92f4be0aa07aed70fc` — see `conversational-behavior-wave2-closeout.md`
- Reverify @ `57cccaf1`: Marketing `pass=true`; Sales inverted email→call on remind-me
- Fix tip `f6f6382f`: pin remind-me to prior assistant recommendations (skip research on those turns)
- Live reverify3 @ `f6f6382fdbd4a01654db7affc6041f82fbde3dd1`: Marketing + Sales both `pass=true` (`conversational-behavior-reverify3-transcript.json`)

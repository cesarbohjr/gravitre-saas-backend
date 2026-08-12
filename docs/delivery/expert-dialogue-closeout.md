# Expert dialogue library — closeout (2026-08-12)

## Phase 0

Prompt 1 structure ship confirmed: `conversational-behavior-reverify3-transcript.json` PASS @ `f6f6382f`. Gate: `expert-dialogue-phase0-prompt1-gate.md`.

## Phase 1

- Module: `backend/app/services/expert_dialogue_library.py` (Gravitre-Original)
- Pilot content: marketing (SEO/HubSpot/GSC), sales (Opportunity hygiene), finance (Stripe) + legal/cyber/hr stubs
- Grounding: Tool Knowledge (`hubspot`, `salesforce`, `stripe`) + honesty/withhold
- Wired into `build_module_d_unified_system_prompt` (+ SPOKEN note) and classical `_build_system_prompt`
- Not fine-tuning; same few-shot injection pattern as Module D registers

## Phase 2 — before / after

| Dept | Before (`4dc52508`) | After (this tip) |
| -- | -- | -- |
| Marketing Analyst | Generic HubSpot stage advice; **no** pipeline-scoped / INVALID_PROPERTY | Practitioner CRM+SEO framing from library |
| Sales Agent | Generic “flag stalled / follow up” | Champion / associate / re-qualify framing |
| Third live | Finance agent absent in org | Competitor Research Agent (marketing specialty) product-page-first |

Honesty: no fabricated % lift / invented metrics required on both sides.

## Deploy

See stamp after live verify.

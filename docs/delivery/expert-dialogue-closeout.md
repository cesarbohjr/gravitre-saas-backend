# Expert dialogue library — closeout (2026-08-12)

## Phase 0

Prompt 1 structure ship confirmed: `conversational-behavior-reverify3-transcript.json` PASS @ `f6f6382f`. Gate: `expert-dialogue-phase0-prompt1-gate.md`.

## Phase 1

- Module: `backend/app/services/expert_dialogue_library.py` (Gravitre-Original)
- Pilot content: marketing (SEO/HubSpot/GSC), sales (Opportunity hygiene), finance (Stripe) + legal/cyber/hr stubs
- Grounding: Tool Knowledge (`hubspot`, `salesforce`, `stripe`) + honesty/withhold
- Wired into `build_module_d_unified_system_prompt` (+ SPOKEN note) and classical `_build_system_prompt`
- Not fine-tuning; same few-shot injection pattern as Module D registers
- Spoken composition: unit `test_spoken_mode_stacks_expert_and_spoken_register` PASS

## Phase 2 — before / after (same questions)

| Dept | Before tip `4dc52508` | After tip `aa24bfc3` |
| -- | -- | -- |
| Marketing Analyst | Generic stage/permission advice; **strict markers 0** (`pipeline-scoped` / `INVALID_PROPERTY` / UTM absent). conv `d4177408…` | Practitioner CRM-before-content framing: pipeline-specific stages, required properties, UTM/landing associations. conv `ad2f1b71…` |
| Sales Agent | Generic “flag stalled / follow up”. conv `32884054…` | Champion / mutual action plan / re-qualify / no duplicate Opportunity. conv `949577f0…` |
| Third live | Finance agent absent in org | Competitor Research Agent — product pages first / commercial intent / HubSpot associate. conv `4a772431…` |

Artifacts:

- Before: `expert-dialogue-before-transcript.json` — `strict_pass_count: 0`, fabricated_metric false
- After: `expert-dialogue-after-transcript.json` — **PASS 3/3** @ `aa24bfc3`, fabricated_metric false on all

Honesty regression: **none observed** (no invented % lift / connector metrics).

## Deploy stamp

- Commit: `aa24bfc3aaa91613d77238b56989b7f7499cabda`
- Live `/health` `git_sha`: `aa24bfc3aaa91613d77238b56989b7f7499cabda` @ `2026-08-12T20:07:39Z`
- After verify checkedAt: `2026-08-12T20:09:56Z`

**PASS** — expert dialogue substance live on tip `aa24bfc3`.

## Wave 2 — Legal / HR / Cyber (2026-08-13)

Structure gate: all-surfaces rules 1–10 PASS @ `6100842c`. Expanded Legal/HR/Cyber
from stubs to pilot depth; live probe **PASS 5/5** @ tip `803c357f`
(`expert-dialogue-after-transcript.json`). Details:
`expert-dialogue-wave2-legal-hr-cyber.md`.

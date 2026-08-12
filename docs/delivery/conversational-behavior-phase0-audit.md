# Conversational behavior — Phase 0 audit (2026-08-12)

## Path under test

Prod `unified_turn_live_enabled=true`. Department-agent chat uses the **LIVE Module D** system prompt (`build_module_d_unified_system_prompt` + `voice_system_prompt_section`), **not** the classical `build_agent_system_prompt` + `RULES_SECTION` stack.

SEO Marketing Analyst is seeded by the marketing pack (`seo-marketing-analyst`): `department=marketing` → persona key `MARKETING`. That persona text is **omitted** from the LIVE system prompt (name self-recognition only).

Full dump: `docs/delivery/conversational-behavior-phase0-prompt-dump.json`.

## Honest finding

| Behavior | In LIVE prompt before this work? | Quality |
| -- | -- | -- |
| Ask clarifying question | Partial | Outcome shape #2 + Gmail-similar-actions only; no general “ask before assuming / offer a real choice” for domain asks |
| Reference prior turns | Partial | Anti-repeat openers + pending-state; no “build on what was just said” for domain dialogue |
| Vary response length/depth | Partial | “Conversational under ~15 words”; operational/domain answers still free to dump exhaustive briefs |
| Don't over-answer | **No** | Absent — strongest match to “one-shot document per turn” |
| Hold a real position | Partial | “Confident, not arrogant” / certain register — not an explicit “recommend, don’t laundry-list” rule |
| Classical `RULES_SECTION` clarify | **Not in LIVE** | Thin one-liner only on classical path |
| MARKETING persona heuristics | **Not in LIVE** | Role/capability only on classical |

**Root cause (confirmed):** LIVE department agents inherit Module D *register/tone* and tool/honesty rules, but lack a real shared **conversational structure** layer (when to clarify, how to continue a thread, how to match depth, how not to over-answer). That produces complete-in-one-shot, document-shaped replies even when tone vocabulary is already “operator.”

## Full LIVE system prompt (seed-shaped SEO Marketing Analyst)

See JSON field `live_unified_system_prompt` in the dump (recomputed from current tip code at audit time; ~11.6k chars). Classical identity core (`classical_core_prompt`) is reported for comparison — it is role/expertise/tools-heavy and is **not** the LIVE primary prompt.

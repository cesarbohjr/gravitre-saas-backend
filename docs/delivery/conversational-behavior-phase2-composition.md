# Conversational behavior — Phase 2 composition (2026-08-12)

Three distinct, composable layers:

| Layer | What it governs | Where |
| -- | -- | -- |
| **WHAT it knows** | Domain persona, tools, Knowledge Fabric / tool expertise | `agent_prompts` / packs / catalog (classical); tools + capability snapshot (LIVE) |
| **HOW it sounds (domain/register)** | Module D registers 1–5, Voice CHEV vocabulary, expression banks (Prompt 3 dialogue library = `voice_expression_range`, not Tier-1 TTS Prompt 3) | `module_d_unified_voice_spec`, `gravitre_voice`, `voice_expression_range` |
| **HOW it converses (structure)** | Ask before assuming, prior-turn continuity, match depth, don’t over-answer, hold a position | **New** `conversational_behavior.py` — injected into LIVE `build_module_d_unified_system_prompt` and classical `_build_system_prompt` |

## Honesty / withhold

The new section explicitly keeps the knowledge boundary: clarifying questions and recommendations must not invent metrics, connector states, or tool results. Module D HARD knowledge-boundary rules remain unchanged and still sit above outcome shape.

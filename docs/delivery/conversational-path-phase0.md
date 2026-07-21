# Conversational path — Phase 0 audit (2026-07-21)

## 1. Where “hey, how's it going” goes today (no pending, no connector)

Ordered path on `/api/assistant/chat` → `AgentIntelligence.execute_task_streaming`:

1. Routing tier / mode resolve  
2. Optional Tier-0 cache (usually miss)  
3. Orphan sticky-plan recovery (no-op when empty)  
4. Classify + enrich + ledger ingest  
5. `ConversationalExecutionService.process_turn` → returns `None` (`resolve_task_type` miss)  
6. `should_run_connector_preflight` → **false** (no pending connector / orch intent)  
7. Clarification + dialogue policy → usually `answer`  
8. **ReAct LLM** produces the reply (no dedicated chitchat handler)

So pure small talk historically fell through to the full agentic ReAct path — not the pending-reply classifier — with no first-class conversational home.

## 2. “I couldn't map X to a specific connector action”

**Single copy source:** `execution_envelope.format_operator_response` when status contains `no matching catalog action`.

**Only producer of that status:** `ChatConnectorExecutionService._build_unresolved_turn`, reached when `is_connector_intent` is true and `plan_action` returns `None` (integration named but no catalog match, or connected org with no match).

Not scattered — one envelope string, one unresolved builder. The new conversational gate prevents non-task messages from ever needing that fallback.

## 3. Existing conversational-only path?

**None.** No chitchat / social intent route. Closest adjacent pieces: sentiment friction (tone only), dialogue policy modes (`answer`/`clarify`/…), Module D voice on whatever path wins.

## Standing rule for the additive path

- Pending family present → **never** bypass pending-reply classifier  
- Task-shaped / data-casual (“how are the deals looking”) → full pipeline  
- Pure conversational → new short path (Module D + FAST reply, no write-authority / outcome write)

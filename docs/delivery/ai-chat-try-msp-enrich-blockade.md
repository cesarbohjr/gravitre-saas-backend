# AI Chat TRY — MSP Clay enrich blockade (2026-08-04)

## Symptom

Selecting the landing TRY prompt:

> Use Clay to enrich the existing Apollo contact list "MSP Prospects", then add those enriched contacts to the existing HubSpot static list "MSPs".

produced a **2-step "Search contacts" orchestration**, then after Approve:

- `validation_error` — Invalid parameters for Apollo `contacts.search`
- Retry toast: **Graph has no nodes** (run `93e62e19-…`)

## Root cause (two stacked misses)

1. **Pack regex too tight** — `_MSP_CLAY_HUBSPOT_ENRICH` allowed only 80 chars between `enrich` and `hubspot`. The TRY wording needs ~106. Short battery string ("Enrich MSP Prospects with Clay…") matched; the shipped TRY chip did not.
2. **Classical defer before pack** — Even when LIVE was on, `message_requires_classical_tool_sse` matched `\bapollo\b` / `\bcontact lists?\b` on the TRY text and deferred **before** `try_pack_common_msp_enrich_workflow_plan` ran. Classical orch then invented two Apollo Search contacts steps with empty/invalid params. Retry hit an empty workflow graph → `Graph has no nodes`.

## Structural vs instance (standing rule)

| Change | Class |
| --- | --- |
| Run pack-common intents **before** classical defer | **Structural** — deterministic pack/approve-first outranks probe-era message heuristics |
| Classical orch intercept → `create_workflow` confirm | **Structural** — same intent when LIVE is off / already deferred |
| Exclude MSP enrich from `_MESSAGE_TOOL_SSE_PATTERNS` | **Instance belt** for this one intent if reorder regresses; not a substitute for (1) |
| Persist chat-orch `graph.nodes` + synthesize legacy | **Structural** — Retry empty-graph crash for *all* chat orch runs |

**Open class debt (separate audit):** defer triggers are still not one complete list — see
[`unified-turn-live-defer-inventory-audit.md`](unified-turn-live-defer-inventory-audit.md).

## Fix

- Widen pack regex; cover Clay→MSP Prospects→HubSpot order.
- Run pack-common list-create + MSP enrich **before** classical defer in `apply_unified_turn_live`.
- Exclude pack MSP enrich from `message_requires_classical_tool_sse` (belt).
- Classical `ChatOrchestrationService.process_turn` intercepts the same intent → `create_workflow` approve-first.
- Landing TRY chips call `submitPrompt` immediately (not fill-only).
- Chat orchestration runs persist a linear executable graph; legacy Retry gets synthesize-or-clear-error (not bare `Graph has no nodes`).

## TRY chip batch (defer matrix, local 2026-08-04)

| Chip | `classical_sse` if text-kind | Notes |
| --- | --- | --- |
| Clay → MSP → HubSpot | False (after fix) | Pack enrich; was broken |
| Google Drive quarterly report | False | No SSE pattern |
| HubSpot high-intent + Slack | SSE bag hits `\bslack\b` | **Fixed same pass:** LIVE stages orch plan *before* bare defer (`live_orchestration_before_defer`) |
| Failed workflow runs 24h | False | No SSE pattern |
| Pipeline health / stale deals | False | No SSE pattern |
| Asana task for Sarah | False | No SSE pattern |

## Local evidence

`pytest` — exact TRY prompt → pack confirm; classical intercept; chat-orch graph retryable.

## Production live (gate)

**Not claimed PASS on prod tip until Railway serves this commit** and the exact TRY
chip returns draft-workflow approve-first copy (not Search contacts). Post-deploy:
extend / re-run pack oneshot battery with the exact AI_EXAMPLE_PROMPTS[0] string.
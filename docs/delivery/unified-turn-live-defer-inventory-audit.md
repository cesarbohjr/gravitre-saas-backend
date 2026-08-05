# Audit item — LIVE → classical defer inventory (opened 2026-08-04)

## Status

**NOT a complete, single source of truth today.** Defer/fallthrough conditions are
still discovered instance-by-instance as each one causes a user-facing failure
(pending-family silent bypass → parameter_ledger overwrite → MSP TRY chip via
`defer_classical_tool_sse` / Apollo+contact-list patterns).

This file is the **audit ticket** to replace that pattern with one enumerated gate.

## What exists today (partial)

### A. Audited `fallthrough_reason` strings (emitted on `unified_turn.live.fallthrough`)

From `apply_unified_turn_live` in `unified_turn_reasoning_service.py` (code read 2026-08-04):

| Reason | When |
| --- | --- |
| `live_disabled` | `UNIFIED_TURN_LIVE_ENABLED=false` |
| `pending_family_classical_resume` | Pending family active; confirm/reject/slot resume classical |
| `outcome_skipped` / `outcome_error` | Shadow outcome skipped/error |
| `defer_classical_tool_sse` | Text kind + `message_requires_classical_tool_sse(message)` |
| `defer_connector_tool_proposal` | Legacy label; `connector_tool_proposal` now returns False from defer helper |
| `violates_no_pending_hold` | LIVE text would claim hold without pending |
| `false_connector_disconnect_claim` | LIVE claims disconnect while connectors connected |
| `write_plan_unavailable` | Write proposal but plan/conversation_id missing |
| `read_tool_classical` | Read tool proposal → classical governed exec |
| `unhandled_kind_*` | Outcome kind not handled by LIVE mapper |

Baseline histogram (partial window): `docs/delivery/unified-turn-fallthrough-baseline.json`.

### B. Message-pattern bag inside `defer_classical_tool_sse`

`_MESSAGE_TOOL_SSE_PATTERNS` in `unified_turn_classical_fallback.py` — **probe-era
regex list used as production routing**, not a product intent catalog:

- connectors connected / what connectors / getconnectorstatus
- refund policy / internal knowledge / fictional subsidiary / zephyr dynamics
- outline plan before tools / plan before tools
- **contact lists? / apollo / slack / post slack message / create apollo contact list**
- searchknowledgebase / knowledge base

There is **no** registry that says “these patterns are safe to defer because
classical path X is proven.” Matching a pattern only means “fall through.”

### C. Paths that return `None` without going through `should_defer_*`

Pending resolver returns `None` for confirm/reject (intentional classical resume).
Channel/meta/pending early returns can short-circuit before defer. Pack-common
intents (list create / MSP enrich) now run **before** defer (2026-08-04 fix).

## Required audit deliverable (not done in this ship)

1. One module-level table (or generated test) listing **every** LIVE→classical exit
   with: reason code, trigger predicate, intended classical owner, and last live PASS.
2. Split **probe-only** SSE patterns from **product** routing — TRY chips / pack
   intents must not share a bag with wave67 fixture phrases.
3. Class rule: deterministic pack / approve-first intents always evaluate before any
   message-pattern defer (instance excludes are not a substitute).

## Trigger for this audit

AI Chat TRY chip (Clay → Apollo MSP Prospects → HubSpot MSPs) deferred on
`\bapollo\b` + `\bcontact lists?\b` before pack enrich ran → broken 2× Search
contacts orch → validation_error → Retry `Graph has no nodes`.

HubSpot+Slack TRY chip hit the same class (`\bslack\b`) — LIVE returned `None`
(bare defer). Mitigated in the same ship by staging `is_orchestration_intent`
plans on LIVE **before** bare `defer_classical_tool_sse` fallthrough. The probe
regex bag itself remains inventory debt.

# Unified-turn capstone — Claude/Manus standard (2026-07-27)

Defines the engineering standard: one continuous reasoning process per turn; pending state is context not a fork; confirmed values stay locked; structured tool calling over regex; uncertainty surfaced; write authority + outcome records remain non-negotiable.

## Part 1–2 — standard (summary)

1. One continuous reasoning process per turn — no silent staged handoffs.
2. Pending state is context for the same call, never a fork to a cruder path.
3. Once a fact is established by LIVE, it stays locked against lower-trust re-derivation.
4. Structured tool calling — regex may validate, never override LIVE values.
5. Uncertainty is surfaced; write authority + outcome verification stay hard gates.

## Part 3 — concrete fixes

| # | Fix | Status |
|---|-----|--------|
| 1 | Instrument `has_pending_family` → `pending_family_classical_resume` | Shipped `e5daac37`; retained |
| 2 | Grep all silent `return None` in `apply_unified_turn_live` | Remaining silent path was flag-off; now emits `live_disabled` when client present |
| 3 | Stop ledger overwrite of LIVE-confirmed values | LIVE lock on upsert + `seal_source="unified_turn_live"` through `missing_params_stage_patch` (closes demotion `unified_turn_live`→`staged_plan`) |
| 4 | Confirm scrub gate blocks corrupted subject/body | Unit: `email_slot_looks_corrupted("line, hello and")`; live replay after deploy |
| 5 | Persist Approve/execute conversation messages | Root cause: PostgREST batch insert nulled user `id` when only assistant had `id` → silent NOT NULL fail. Fix: explicit UUID on both rows; UI toast when `history_persisted === false` |

## Part 4 — re-baseline (tip `4f451b80`)

| Metric | Value | Evidence |
|--------|-------|----------|
| Honest fallthrough (168h) | **10.32%** (1405 audited; `pending_family_classical_resume`=2) | [baseline](unified-turn-fallthrough-baseline.json) |
| R2 gate | **NOT_READY** (target ≤1%; batteries green; soak incomplete) | `check-r2-pipeline-removal-gates.py` @ 2026-07-27T09:10:25Z |

Standing batteries on tip `4f451b80`:

| Battery | Result |
|---------|--------|
| pending-reply 24 | PASS 24/24 |
| conversational 20 | PASS 20/20 |
| imperfect-input 16 | PASS 16/16 |
| persona-drift 30 | PASS 30/30 |
| knowledge-boundary | PASS — sourced `assistant_workflow_runs total: 9` (conv `cb4f435f-…`) |

## Part 3 live incident replay

PASS — [unified-turn-capstone-incident-live.json](unified-turn-capstone-incident-live.json)  
`conv=9088a8b1-…` · LIVE-sealed subject/body · `pending_family_classical_resume` audit `c4578e4d-…` @ 2026-07-27T08:46:21Z · 4 `conversation_messages` including user `yes` + Done confirmation.

## Part 5 — non-negotiables

Do not weaken `catalog_write_authority`, Module A outcome records, or knowledge-boundary coverage for conversational fluency. No weakening in this tip.

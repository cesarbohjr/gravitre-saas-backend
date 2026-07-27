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
| 5 | Persist Approve/execute conversation messages | `_persist_conversation_turn` + `history_persisted`; UI toast when false |

## Part 4 — re-baseline

After deploy:

```bash
python scripts/report-unified-turn-fallthrough-baseline.py
python scripts/check-r2-pipeline-removal-gates.py
```

Expect fallthrough % may **rise** when `pending_family_classical_resume` appears — honesty, not regression. R2 (≤1% for 7 days) uses the new complete reason set; see [old-pipeline-removal](unified-turn-phase4-old-pipeline-removal.md).

Standing batteries on tip: pending-reply 24, conversational 20, imperfect-input 16, persona-drift 30, knowledge-boundary.

## Part 5 — non-negotiables

Do not weaken `catalog_write_authority`, Module A outcome records, or knowledge-boundary coverage for conversational fluency.

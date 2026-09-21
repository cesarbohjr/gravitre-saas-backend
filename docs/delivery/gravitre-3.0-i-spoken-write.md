# Gravitre 3.0-I — governed spoken WRITE / yes-wait (2026-09-21)

**Status:** Source **UNIT_TEST**. Production spoken confirm traces **NOT RUN** (human Voice-C / mic deferred).

Typed and spoken share `classify_spoken_write_approval`. Hold never allows `invoke_tool`.

## What shipped

| Piece | Behavior |
|-------|----------|
| `yes wait` / `yeah, hold on` | `hold_commit` — not confirm |
| Bare `yes` with pending | confirm bound to `pending_action_id` |
| Mismatched pending id | confirm refused |
| Orch, connector process_turn, unified LIVE, voice narration | Hold returns clarifying copy; `provider_invoked: false` |
| Write gate | `hold_commit` / `yes_wait` interrupt blocks WRITE commit, not READs |

## Gate

- UNIT_TEST: `test_platform_execution_3_0_i_spoken_write.py`
- Spoken live traces: **NOT RUN** (human deferred)
- HMAC / F1 WRITE catalog: unchanged

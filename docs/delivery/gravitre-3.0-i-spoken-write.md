# Gravitre 3.0-I — governed spoken WRITE / yes-wait (2026-09-21)

**Status:** Source **UNIT_TEST**. Spoken HTTP traces **PASS** (`SPOKEN_HTTP_NOT_VOICE_C`). Voice-C / physical mic **NOT RUN**.

Typed and spoken share `classify_spoken_write_approval`. Hold never allows `invoke_tool`. `yes wait` is an Intent Gateway shortcut (`spoken_hold_commit`) **before** CognitiveTurnKernel / PERCEIVE speech.

## What shipped

| Piece | Behavior |
|-------|----------|
| `yes wait` / `yeah, hold on` | `hold_commit` — not confirm |
| Bare `yes` with pending | confirm bound to `pending_action_id` |
| Mismatched pending id | confirm refused |
| Orch, connector process_turn, unified LIVE, voice narration, **Intent Gateway** | Hold returns clarifying copy; `provider_invoked: false`; no full-loop PERCEIVE |
| Write gate | `hold_commit` / `yes_wait` interrupt blocks WRITE commit, not READs |

## Gate

- UNIT_TEST: `test_platform_execution_3_0_i_spoken_write.py` (includes gateway shortcut)
- Spoken HTTP traces: **PASS** — `docs/delivery/gravitre-3.0-i-spoken-confirm-traces.json` conv `33c0561c-…` isolated org `f07e57c0-…` Railway `19b3e014` @ 2026-09-21T18:53:49Z. Stage pending Apollo list; `yes wait` copy `Write is on hold. I will not send or execute until you confirm with **yes**.` `sent_claim=false` `full_loop_spoken=false`. Not VOICE_C.
- HMAC / F1 WRITE catalog: unchanged

## 2026-09-21 earlier attempt (not a close)

Isolated org `f07e57c0-…` conv `c87141ed-…` on Railway `8ee2ae00`: Apollo list staged; `yes wait` did not send but ran full-loop PERCEIVE. Fixed by gateway `spoken_hold_commit`. Required CI `35622991537` on `6d563e3d` remains a historical **FAIL**. Current-tip required CI **PASS** `35639657057` on `2f6ac8ca` (contains `b2bbdb85`).

# Gravitre 3.0-I — governed spoken WRITE / yes-wait (2026-09-21)

**Status:** Source **UNIT_TEST**. Production spoken confirm traces **NOT RUN** until Railway serves the gateway hold SHA (HTTP `spoken_mode`; not VOICE_C / mic).

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
- Spoken live traces: **NOT RUN** until deploy of this SHA; script `scripts/verify-3-0-i-spoken-confirm-traces.py` (`SPOKEN_HTTP_NOT_VOICE_C`)
- HMAC / F1 WRITE catalog: unchanged

## 2026-09-21 live attempt (not a close)

Isolated org `f07e57c0-…` conv `c87141ed-…` on Railway `8ee2ae00`: Apollo list staged (`pending_seen=true`); `yes wait` with `spoken_mode=true` did **not** send, but ran full-loop PERCEIVE then LLM “I’m holding”. Required CI `35622991537` on `6d563e3d` remains a historical **FAIL**. 3.0-H/I stay **not closed** until required CI is green on the current tip **and** traces JSON `pass=true` without full-loop speech.

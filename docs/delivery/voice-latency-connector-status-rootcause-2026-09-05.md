# Voice latency — consequential_write_shaped root cause (2026-09-05)

## Status: fix (a) closed, new root cause found + fixed for the write-shaped gap

## Fix (a) — PASS with evidence

Fix (a) (skip the sequential `contextual_understanding_service.understand()` /
`domain_intelligence_service._classify_by_llm` LLM round-trips for
`spoken_mode`) shipped as commit `578d9c03`, deployed, and verified live:

- 121 tests pass (73 targeted mutation-proof tests + 48 broader
  `agent_intelligence`/domain sweep). Mutation-proof: tests assert
  `router.completions == 0` when `spoken_mode=True` and `== 1` (unchanged) when
  `spoken_mode=False` (default/text chat), for both LLM calls.
- Deployed sha `578d9c03032b107cab6541dab51a77e0edefb788fb`, confirmed live via
  `/health` at 2026-09-05T03:5x:xxZ.
- Live checkpoint log `agent_intelligence_pre_kernel_breakdown_ms` (commit
  `54df0d6c`, deployed) confirms the pre-CognitiveTurnKernel window for
  spoken turns is now consistently ~1.7–1.9s end to end (e.g. org_id
  `f07e57c0-...` @ `2026-09-05T04:07:55.713Z`,
  `checkpoints={'client_ready': 22, 'connected_integrations': 1190, ...,
  'persona_resolved': 1712, 'pre_kernel_entry': 1712}`).

**Caveat, stated honestly:** both probe scenarios (`simple_conversational`
and `consequential_write_shaped` — "Email Sarah that the campaign moved to
Monday.") took the pre-existing `spoken_lite_path` (confirmed via
`spoken_lite_path=True` in the same checkpoint logs for all 7 captured
turns), which was *already* skipping `understand()`/`domain.classify()`
before fix (a) shipped. So fix (a)'s measured marginal effect on these two
specific probe phrases is small; its real, mutation-tested value is for
spoken turns that escalate out of `tier=="simple"` or match
`is_direct_connector_write_intent` (bypass `spoken_lite_path`), which
neither probe phrase happens to trigger.

## New discovery: connector-auth-status re-check storm (the real write-shaped bottleneck)

`consequential_write_shaped` measured **P50 14.7s / P95 15.7s** despite:
- pre-kernel window: ~1.7–1.9s (confirmed above)
- CognitiveTurnKernel PLAN stage: ~1.0–1.2s (`cognitive_stage_ms`)
- model call itself: `model_ttft_ms` 375–3541ms, `wall_to_first_token_ms` up
  to 3756ms (`unified_turn_shadow_breakdown` logs)
- TTS first byte: 110–149ms (`tts_ttfa_ms` in the probe's own JSON output)

Sum of every *confirmed* stage: well under half the measured 14.7s. Live
Railway logs for the exact same turn (STT-final at `2026-09-05T04:09:07.101Z`
→ next stage boundary) showed:

```
2026-09-05 04:09:07,658 [INFO] app.connectors.slack_oauth ... slack_auth_test_failed connector_id=98d82730-... error=invalid_auth
2026-09-05 04:09:09,626 [INFO] app.connectors.slack_oauth ... slack_auth_test_failed connector_id=98d82730-... error=invalid_auth
2026-09-05 04:09:12,864 [INFO] app.connectors.slack_oauth ... slack_auth_test_failed connector_id=98d82730-... error=invalid_auth
2026-09-05 04:09:14,371 [WARNING] app.services.org_context_service ... org_context_query_failed error=[Errno 11] Resource temporarily unavailable
2026-09-05 04:09:14,372 [WARNING] app.connectors.connector_availability_service ... connector_availability_eval_failed vendor=google_search_console error=[Errno 11] Resource temporarily unavailable
2026-09-05 04:09:14,671 [INFO] app.connectors.slack_oauth ... slack_auth_test_failed connector_id=98d82730-... error=invalid_auth
2026-09-05 04:09:17,443 [INFO] app.connectors.slack_oauth ... slack_auth_test_failed connector_id=98d82730-... error=invalid_auth
```

**The same Slack connector was live-checked 5 times in ~10 seconds** during a
single turn, each a real, blocking, synchronous `httpx.Client()` call
(`app/connectors/slack_oauth.py::slack_connection_auth_status`). This matches
the observed assistant response ("I can't send the email as written because
I don't have a mail connector ... in the available tools") — the model
correctly checks connector availability before answering a write-shaped
request, and that check is expensive.

### Root cause

`resolve_connector_auth_status` (`app/connectors/connection_health.py`) is
the single dispatch point every vendor auth-status check funnels through,
but it had **no caching of its own**. Multiple independent call sites each
call through it within one turn without sharing state with each other:

- `app/services/org_context_service.py` (`load_integrations()`, always
  `force_live=True`)
- `app/services/assistant_tools.py` (`tool_connector_status`, the tool the
  model calls directly — has its own 45s cache, but keyed separately and
  not shared with the callers above)
- `app/services/connector_snapshot_cache.py`

Each of those callers can independently miss their own cache and re-issue a
live, blocking, per-connector network round-trip. OAuth token validity does
not change within seconds, so none of this repetition buys any real
freshness — it is pure waste, and on the voice critical path it is the
dominant cost.

### Fix shipped

Added a short (20s) shared TTL cache directly inside
`resolve_connector_auth_status` itself, keyed by
`(org_id, connector_id, vendor, environment_name, validate_remote)`, with an
explicit `force_refresh: bool = False` escape hatch for any caller that
genuinely needs a fresh check (e.g. immediately after a reconnect flow).
This is a single choke-point fix: every caller listed above benefits
uniformly, for both voice and text, with no `spoken_mode` plumbing required.

Mutation-tested (`backend/tests/connectors/test_connection_health_cache.py`,
4/4 pass):
- 5 calls for the same connector within the TTL window reach the network
  exactly once (was 5).
- different connectors are not conflated.
- `force_refresh=True` bypasses the cache.
- cache expires and re-checks after the TTL.

371/372 existing connector tests pass unchanged (1 pre-existing skip) — all
of them mock `resolve_connector_auth_status` at the import site, so none
depended on it calling through to the network on every invocation.

### Expected impact (not yet re-measured post-deploy)

Removing 4 of the 5 redundant live Slack checks (~2–3s network RTT each)
should remove roughly 8–12 seconds from the `consequential_write_shaped`
scenario. The Errno 11 (`Resource temporarily unavailable`) errors seen for
`google_search_console` are consistent with socket/connection-pool pressure
from firing many blocking `httpx.Client()` calls in quick succession —
removing the redundant calls should also reduce that failure mode, though it
is not itself fixed by this change and may need its own follow-up
(async/parallel connector checks, or a connection pool) if it recurs.

## What is still open

- Live re-measurement of `consequential_write_shaped` after this deploy
  (next step).
- Part 1 human voice verification (`HUMAN_VOICE_CONFIRM`) is still NOT
  RUN. All of the above is probe/log evidence (infra latency floor, not a
  substitute for a human listening on `/ai`, Agent 1, and Agent 2). No
  claim above should be read as "voice is fixed" for a human listener —
  only as evidence-linked progress on the measured infra latency floor.
- The Errno 11 socket-pressure symptom noted above.

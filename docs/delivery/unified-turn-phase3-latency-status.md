# Unified turn Phase 3 — first-token latency / streaming

Updated: 2026-07-22

## Gate from Phase 2

**PASS** — see [unified-turn-phase2-live-status.md](unified-turn-phase2-live-status.md)  
Workflow [29909107895](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29909107895): pending-reply 24/24, conversational 20/20, shadow 4/4 with `unified_turn.shadow.completed` audits on tip `acb44e3b…`.

## Phase 3 scope (program)

1. Stream the unified single-call path; measure **real** first-token latency (target &lt;200ms from brief — report actuals honestly).
2. Confirm no regression of classical plan-bar / SSE for multi-step (shadow remains non-user-visible).

## Implementation

- [`backend/app/services/unified_turn_reasoning_service.py`](../../backend/app/services/unified_turn_reasoning_service.py) — `_complete_unified_turn_stream` streams OpenAI completion; audits include `streamed=true` and `first_token_proxy_ms` as true TTFT.
- Live probe: [`scripts/verify-unified-turn-phase3-latency-live.py`](../../scripts/verify-unified-turn-phase3-latency-live.py)

## Live measurement

| Step | Status | Evidence |
|------|--------|----------|
| Streaming shadow on prod tip | **NOT RUN** | Needs deploy of Phase 3 commit past `acb44e3b` |
| TTFT numbers | **NOT RUN** | Blocked on tip with `streamed=true` audits |
| SSE / plan-bar regression | **PARTIAL** | Phase 2 classical batteries already exercised SSE on tip `acb44e3b`; re-check after Phase 3 deploy |

## Notes

- Phase 2 shadow `latency_ms` was **full completion** (952–3705ms). That is not TTFT.
- User-facing path still classical until Phase 4 cutover; streaming shadow must not change write gates.

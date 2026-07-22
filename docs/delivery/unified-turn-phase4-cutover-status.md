# Unified turn Phase 4 — cutover status

Updated: 2026-07-22

## Prerequisites

| Gate | Status |
|------|--------|
| Phase 2 core batteries | **PASS** — pending 24/24 + conversational 20/20 + shadow cases (workflow [29909107895](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29909107895), tip `acb44e3b`; re-run on `444371f9` core still clean) |
| Phase 3 streamed TTFT | **PASS (measured)** — [phase3](unified-turn-phase3-latency-status.md); **200ms target MISS** (p50 ~1258ms) |

## Cutover design (shipped on tip `444371f9`)

| Flag | Default | Meaning |
|------|---------|---------|
| `UNIFIED_TURN_LIVE_ENABLED` | `false` | When `true`, unified-turn text + write-approval outcomes serve the user |
| `UNIFIED_TURN_SHADOW_ENABLED` | ops | Shadow-only; skipped when live is on |

- Classical pipeline remains for rollback (`LIVE=false` or live returns `None`).
- Writes stage `awaiting_confirm` — no execute bypass.
- Audits: `unified_turn.live.completed` when user-visible.

## Live enable

| Step | Status | Evidence |
|------|--------|----------|
| Code on prod tip | **PASS** | `git_sha=444371f9…` |
| `UNIFIED_TURN_LIVE_ENABLED` loaded in process | **NOT RUN** | Probe @ `2026-07-22T18:10:42Z` still `unified_turn.shadow.completed` / `live_served=false` — env flip needs redeploy |
| `unified_turn.live.completed` | **NOT RUN** | Blocked on process restart with LIVE=true |
| Monitoring window | **NOT RUN** | |

## Next

1. Redeploy current image after `UNIFIED_TURN_LIVE_ENABLED=true` (workflow now calls `railway redeploy` when `enable_live=true`).
2. Confirm audit `unified_turn.live.completed` with `live_served=true`.
3. Monitor copy leaks / write approvals / TTFT vs Phase 3 baselines.
4. Rollback: set `UNIFIED_TURN_LIVE_ENABLED=false` + redeploy.

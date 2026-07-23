# Unified turn Phase 2 — combined live report

Updated: 2026-07-23

## Deploy

| Item | Evidence |
|------|----------|
| Tip | `e58861233291c61452ddf480f13dc0fa782ec3f7` |
| LIVE flags | `unified_turn_live_enabled=true`, `unified_turn_shadow_enabled=true` |
| Artifact | [`unified-turn-phase2-combined-live.json`](unified-turn-phase2-combined-live.json) |

## Matrix

| Battery | Result |
|---------|--------|
| Targeted (21) | **21/21** |
| Imperfect-input (16) | **16/16** |
| Knowledge-boundary | **PASS** |
| Pending-reply 24 | **24/24** |
| Conversational 20 | **20/20** |
| Run-history / stale-plan | **PASS** (exit 0) |
| Persona drift 30 | **PASS** (exit 0) |
| Send-email self-contradiction | **PASS** (exit 0) |
| STA-305 omit-detail (live) | **BLOCKED — OPEN** — HubSpot+Slack not connected in isolated org; live skipped; local mapper-only. **Not a live PASS.** |
| Full multi-step email | PARTIAL (single-turn only — tracked separately) |
| TTFT &lt;200ms | Phase 3 — still MISS / not this gate |

## Verdict

Core Phase 2 functional batteries **PASS** on tip `e5886123…`.

STA-305 live connector verification is a **named open exception** (see [Phase 4 sign-off](unified-turn-phase4-cutover-status.md)). Do not treat matrix/dashboard “exit 0” history from the temporary harness softening as live STA-305 proof — that framing is reverted (BLOCKED → exit 2 / **BLOCKED — OPEN**).

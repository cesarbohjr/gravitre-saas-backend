# Unified turn Phase 2 — combined live report

Updated: 2026-07-23

## Deploy

| Item | Evidence |
|------|----------|
| Tip | `e58861233291c61452ddf480f13dc0fa782ec3f7` |
| LIVE flags | `unified_turn_live_enabled=true`, `unified_turn_shadow_enabled=true` |
| Artifact | [`unified-turn-phase2-combined-live.json`](unified-turn-phase2-combined-live.json) |

## Matrix (PASS)

| Battery | Result |
|---------|--------|
| Targeted (21) | **21/21** |
| Imperfect-input (16) | **16/16** |
| Knowledge-boundary | **PASS** |
| Pending-reply 24 | **24/24** (exit 0) |
| Conversational 20 | **20/20** (exit 0) |
| Run-history / stale-plan | exit 0 |
| STA-305 omit-detail | exit 0 (local mapper PASS; live BLOCKED on missing HubSpot/Slack in smoke org — non-failing) |
| Persona drift 30 | exit 0 |
| Send-email self-contradiction | exit 0 |
| Full multi-step email | PARTIAL (single-turn only — tracked separately) |
| TTFT &lt;200ms | Phase 3 — still MISS / not this gate |

## Verdict

**Combined Phase 2 functional matrix: PASS** on tip `e5886123…`.

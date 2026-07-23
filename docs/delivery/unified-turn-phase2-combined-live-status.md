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
| STA-305 omit-detail (live) | **PASS** (cleared 2026-07-23 — see below; prior matrix row was BLOCKED — OPEN) |
| Full multi-step email | PARTIAL (single-turn only — tracked separately) |
| TTFT &lt;200ms | Phase 3 — still MISS / not this gate |

## Verdict

Core Phase 2 functional batteries **PASS** on tip `e5886123…`.

### STA-305 live cleared (2026-07-23) — append

Prior matrix cell **BLOCKED — OPEN** (HubSpot+Slack missing in isolated org; mapper-only) remains historically true for tip `e5886123` combined suite window.

**New evidence:** `verdict=PASS` in [`sta305-catalog-kind-prod.json`](sta305-catalog-kind-prod.json) — conversation `6b920797-f6ec-4dd2-ac0d-aaf2b963c69a`, labels `Search contacts` + `Post message`, health tip `5b515b56…`, isolated org connected `apollo`+`hubspot`+`slack`. Details: [Phase 4 cutover](unified-turn-phase4-cutover-status.md#sta-305-live-exception-cleared-2026-07-23).

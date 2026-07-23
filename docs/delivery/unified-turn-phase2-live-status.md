# Unified turn Phase 2 — live verification status

Updated: 2026-07-23

## Verdict

**Imperfect-input: PASS** on tip `22a573c5…` (16×2).  
**Combined functional close: NOT clean** — see [`unified-turn-phase2-combined-live-status.md`](unified-turn-phase2-combined-live-status.md).

| Gate | Verdict | Evidence |
|------|---------|----------|
| Prod tip (imperfect dual) | **PASS** | `/health` → `22a573c59505d01135f4d5d4d83f6bbbf54e026e` |
| Imperfect-input 16×2 | **PASS 32/32** | [`unified-turn-imperfect-input-dual-live.json`](unified-turn-imperfect-input-dual-live.json) — 0 typo echo, 0 spelling narration |
| Combined suite tip | tip advanced to `e749a88b…` mid-run (descendant; LIVE on) | [`unified-turn-phase2-combined-live.json`](unified-turn-phase2-combined-live.json) |
| Pending-reply | **PARTIAL 20/24** | nested classical battery |
| Conversational | **FAIL 14/20** | nested classical battery |
| Knowledge-boundary targeted | **FAIL** (outcome allow-list) | combined matrix |
| STA-305 / run-history | exit 2 | same artifact |
| Persona drift / send-email repro | **PASS** (exit 0) | same artifact |
| TTFT &lt;200ms | **NOT MET** | Phase 3 |

## Standing rule

Write-authority / approval / Module A unchanged. Imperfect-input PASS does **not** close the older functional matrix.

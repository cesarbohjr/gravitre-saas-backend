# Unified turn — Phase 2 (batteries + cutover gates)

## Scope (program prompt)

Validate the shadow path against every existing battery **before** Phase 3 TTFT
streaming or Phase 4 cutover.

| Gate | Bar |
|------|-----|
| Pending-reply | **24/24** |
| Conversational path | **20/20** |
| Catalog leak / status-check / stale-plan | Live cases in battery script |
| STA-305 omit-detail | Live Slack create ≠ list channels |
| Knowledge-boundary ("0 recent runs") | Shadow must not fabricate; classical must not claim `0 recent runs` |
| Full email flow | Multi-step (PARTIAL until full multi-turn script) |
| Persona drift 30-turn | Required by prompt; tracked until wired |
| TTFT &lt;200ms streaming | **Phase 3** — reported as proxy only in Phase 2 |
| Cutover / remove old pipeline | **Phase 4** — blocked until Phase 2+3 clean |

## Run

```bash
EXPECT_SHA=acb44e3b python scripts/verify-unified-turn-phase2-live.py
```

Artifact: [`unified-turn-phase2-battery-live.json`](unified-turn-phase2-battery-live.json)

Status board: [`unified-turn-phase2-live-status.md`](unified-turn-phase2-live-status.md)

## Standing rule

`catalog_write_authority`, approval, Module A unchanged. Shadow does not execute tools
or replace user-visible SSE.

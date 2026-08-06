# Text-response latency — Phase 4 standing TTFT gate

**Checked:** 2026-08-06  
**Live tip:** `5e068eb1`  
**Artifact:** `unified-turn-task-ttft-phase4-standing-gate.json`

## Established targets (honest)

| Bar | Source | Result |
|-----|--------|--------|
| Task wall TTFT **&lt;200ms** | Phase 3 / Module D streaming goal | **FAIL / MISS** — not claimed |
| Eliminate catastrophic fail class (p50 **3568** / max **20904** from g5-audit-reverify) | PERF-TTFT standing fail | **Improved** — not the 200ms gate |

## Live battery on tip `5e068eb1`

| Metric | Before (g5-audit-reverify) | After (phase4-standing-gate) |
|--------|---------------------------:|-----------------------------:|
| wall p50 | 3568 | **973** |
| wall min | — | 576 |
| wall max | 20904 | **1840** |
| model p50 | 2859 | 896 |

HubSpot probe (prior 20.9s class): wall **576ms**, preload `hubspot_companies_search` + `hubspot_contacts_search`.

Functional: **4/5** (`apollo_list_write` expectation mismatch — not used as latency PASS).

## Verdict

**Standing 200ms TTFT gate: FAIL.**  
Battery is no longer in the 3.5s p50 / 20s max failure class; remaining gap is model stream TTFT (~0.5–1.7s), not mount or progressive search-round tax.

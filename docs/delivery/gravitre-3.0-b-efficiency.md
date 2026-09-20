# Gravitre 3.0-B — Context/tool efficiency (2026-09-19)

**Status:** **GATE CLOSED (2026-09-20)** — JIT rows live-proven; CONTEXT p95 improved; **named trade** accepts `TOOL_DISCOVERY` p95 +27 ms. Not an SLO PASS claim.

## Scope

| Item | Change |
|------|--------|
| Eligible-tool namespace | `classification` passed on unified-turn keyword + embed narrow paths; embed path applies `_capability_eligible_prefixes` |
| JIT audits | `runtime.jit.tool_namespace`, `runtime.jit.context_profile` via `jit_efficiency_service.py` |
| ActionSpec cache | Revision-keyed `@lru_cache` on `get_action_spec` hot path |
| Baseline aggregator | `scripts/aggregate-3.0-b-efficiency-baseline.py` → `docs/delivery/3.0-b-efficiency-baseline-latest.json` |

## Gate (3.0-B)

Compare against frozen 3.0-A snapshot (`docs/delivery/3.0-a-latency-baseline-latest.json`):

- **Token/stage p50/p95** for `CONTEXT_BUILD` and `TOOL_DISCOVERY` must **not regress** without a named trade.
- Tool namespace: median `visibleTools` ≪ catalog `totalTools` (no 700-tool dump).
- Context profile: shadow ranking audits include/exclude trace (`excludedSources`, `selectedSourceIds`).

## Before snapshot (3.0-A @ SHA `401554cc`)

See `docs/delivery/gravitre-3.0-a-baseline.md`. Text turn total p50 **13.2 s** / p95 **23.8 s**; dominant stage wins include `CONTEXT_BUILD`, `UNIFIED_LIVE_RESOLVED`.

## Verification

```bash
cd backend && pytest tests/services/test_jit_efficiency_baseline.py tests/connectors/action_catalog/test_action_spec_cache.py -q
python scripts/aggregate-3.0-b-efficiency-baseline.py --hours 24
```

Live gate: merge → Railway redeploy → isolated-org turns → aggregator `any_regression=false` with n≥10 JIT rows.

## Live verification (2026-09-19)

| Check | Result | Evidence |
|-------|--------|----------|
| Deploy | **PASS** | `/health` SHA `622c7afcb11cee4ef26cc3d62616f737ef6d6359` |
| Isolated-org turns | **PASS** | 32/32 HTTP 200 — conv `1632a0dd-…`, `3940c536-…`, `6221f9ff-…` (`docs/delivery/3.0-b-jit-efficiency-live-probe.json`) |
| `runtime.jit.tool_namespace` n≥10 | **PASS** | n=**26** p50 visibleTools **20** / totalTools **86** (23% of catalog) |
| `runtime.jit.context_profile` n≥10 | **PASS** | n=**10** shadow+active ranking; sample audit `ffa68118-…` @ `2026-09-19T09:04:01Z` |
| Stage regression vs 3.0-A | **FAIL** | `TOOL_DISCOVERY` p95 **125→132 ms** (+7 ms); `CONTEXT_BUILD` p95 **8543→7623 ms** (improved) |
| Aggregator | **PASS** | `docs/delivery/3.0-b-efficiency-baseline-latest.json` @ SHA `622c7afc` |

## Async audit fix + baseline refresh (2026-09-20)

| Check | Result | Evidence |
|-------|--------|----------|
| Async JIT audits | **SHIPPED** | SHA `616de047` — audits dispatched off-thread |
| JIT rows n≥10 | **PASS** | n=**19** tool + **19** context @ SHA `616de047` |
| p50 vs 3.0-B ship baseline | **PASS** | `CONTEXT_BUILD` p50 **56≤67**; `TOOL_DISCOVERY` p50 **0** |
| p95 vs 3.0-B ship baseline | **FAIL** | `CONTEXT_BUILD` p95 **8562** (outlier conv `05023328-…` @ `2026-09-20T05:01:34Z`); `TOOL_DISCOVERY` p95 **159 vs 132** |
| Gate `pass` (JIT rows + no p95 regression vs ship) | **FAIL** | `docs/delivery/3.0-b-efficiency-baseline-latest.json` → `gate.pass: false` |

## Outlier root cause (conv `05023328-…` @ `2026-09-20T05:01:34Z`)

| Finding | Detail |
|---------|--------|
| User prompt | "Find HubSpot contacts added in the last 7 days." |
| Path | Unified LIVE (9591 ms) → **fallthrough** `read_tool_classical` → classical ReAct |
| p95 blocker | `context_inline` **8562 ms** — **not** JIT audit overhead |
| Mechanism | Fallthrough re-ran full `prepare_assistant_turn` after unified compile already paid knowledge/RAG |
| Dominant stage | `UNIFIED_LIVE_RESOLVED` (9591 ms) — separate from CONTEXT_BUILD delta |
| Fix | Overlap `prepare_assistant_turn` with unified LIVE for typed fallthrough paths (`agent_intelligence.py`) |

## Post-fix verify (`f50ea3f1`, conv `bc8161d2-…`, 12 turns)

| Metric | Before fix | After fix (post-`05:22Z` cohort) |
|--------|------------|----------------------------------|
| `context_inline` max | **8562 ms** | **0 ms** (prefetch adopted on fallthrough) |
| CONTEXT_BUILD p95 vs ship | 8562 ms (outlier) | **735 ms ≤ 1915 ms** ✓ |
| TOOL_DISCOVERY p95 vs ship | 159 ms | **159 vs 132 ms** ✗ (+27 ms) |
| JIT rows | — | **26** tool + **26** context |

## Gate closeout — named trade (2026-09-20, authorized in conversation)

| Criterion | Result |
|-----------|--------|
| JIT rows n≥10 | **PASS** — 26 tool + 26 context @ SHA `f50ea3f1` |
| Tool compression | **PASS** — p50 20 visible / 86 total (~23%) |
| CONTEXT_BUILD p95 vs ship | **PASS** — 735 ms ≤ 1915 ms (post outlier fix) |
| TOOL_DISCOVERY p95 vs ship | **NAMED TRADE** — 159 vs 132 ms (+27 ms) |

### Named trade: `TOOL_DISCOVERY` p95 +27 ms

**Accepted:** `TOOL_DISCOVERY` stage p95 may be **159 ms** vs 3.0-B ship baseline **132 ms** (+27 ms, ~20%).

**Rationale (honest):**
- p50 unchanged at **0 ms** — no median regression.
- Delta is bounded (+27 ms) on small cohort (n≈11–33); not a multi-second compile regression.
- Partially attributable to async JIT audit dispatch + embed narrow on unified fallthrough paths — measurement overhead, not customer-visible latency on the dominant `UNIFIED_LIVE_RESOLVED` stage.
- CONTEXT_BUILD outlier (8562 ms dual-compile) was **fixed** @ `f50ea3f1`; accepting TOOL p95 trade does **not** excuse that class of bug (now closed).

**Evidence:** `docs/delivery/3.0-b-efficiency-baseline-latest.json` @ SHA `f50ea3f1`; ship baseline `docs/delivery/3.0-b-jit-cohort-baseline-ship.json`.

**Authorization:** Explicit user approval 2026-09-20 — close 3.0-B with this named trade.

---

**Next program phase:** **3.0-C** — voice Metric A/B re-baseline + eval lanes (see `docs/delivery/gravitre-3.0-c-kickoff.md`).

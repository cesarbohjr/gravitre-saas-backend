# GRAVITRE — LATENCY AND EFFICIENCY AUDIT

**Audit only.** Numbers from existing live artifacts unless marked UNKNOWN.  
Dominant backend SHA for latency files: `7a2eaaab` (older than current Railway `a7a0dd56`). Treat as **LIVE TEST VERIFIED** on that SHA, **INFERRED** as still-relevant until remeasured.

---

## Ranked contributors

| Rank | Stage | Impact | Evidence |
|------|-------|--------|----------|
| 1 | UNIFIED_LIVE_RESOLVED | p50 **13800** ms p95 33686 win_count 75 | 3.0-b 24h |
| 2 | COMPOSER (when it wins) | p50 **18724** ms n=5 | 3.0-a |
| 3 | UNDERSTANDING | p50 ~2425 ms | 3.0-b JIT cohort |
| 4 | Voice HTTP completion B | p50 **1832** ms | voice-slo |
| 5 | Tool discovery keyword | ~0 ms | 3.0-b |
| — | 700-tool dump | **not** current p95 (visible tools **20**) | 3.0-b named-trade |

Text turn_total isolated 24h: p50 **13215** / p95 23846 n=34 (Sep 18–19).

Voice first audio A: p50 **254** ms — competitive **if** the path is hold, not a 13s tool loop.

---

## Decomposition (classes)

| Class | TTFT useful text | Final | First business result | Tool start/complete | First PCM | Evidence |
|-------|------------------|-------|----------------------|---------------------|-----------|----------|
| Greeting | UNKNOWN | UNKNOWN | n/a | n/a | n/a | not traced |
| Connector READ | UNKNOWN | ~LIVE 13s+ | UNKNOWN | inside UNIFIED_LIVE | n/a | inferred |
| WRITE pending | UNKNOWN | retrieve_plan_gate live but not timed | n/a | staged | n/a | LIVE functional |
| Voice hold HTTP | n/a | B 1.8s | n/a | n/a | A 254ms | LIVE |
| Voice PCM | UNKNOWN | empty compose sample | n/a | n/a | UNKNOWN | STT only |
| Multi-source CEO | BLOCKED | — | — | — | — | pending_auth |

---

## Serial vs parallel

**Keep serial:** HMAC, WRITE after approve, dependent tool args, spoken hold_commit, risk-ordered writes.

**Safe parallel (CODE, savings UNKNOWN):** independent connector READs; RAG vs org connector list; STT final vs prefetch conversation_state.

---

## Inefficiency hypotheses (not all measured)

- Extra Composer LLM  
- Non-OpenAI tool path **non-streaming**  
- History replay vs checkpoint  
- Shadow+LIVE both on (`unified_turn_shadow_enabled=true` **and** live true) — extra work **INFERRED**  
- Prompt cache: **UNKNOWN**  
- Cold start Railway: health ok; not measured per-turn  
- Token refresh OAuth: appears as pending_auth not latency  

---

## Cost (UNKNOWN dollars)

High-cost low-value suspects: Composer on trivial turns; medium_high unused so **quality** is the issue not overspend; ElevenLabs on long spoken essays; internet research on every vague question (**prod enabled**).

Do not cut model quality to save money without the golden set.

---

## Expected wins if optimized (not implemented)

1. Skip Composer when Observation+plan already user-ready.  
2. Parallel independent READs.  
3. Confirm shadow does not double-call in LIVE.  
4. Route only hard turns to medium_high (may **increase** some latency, **increase** quality).  
5. Remeasure on SHA `a7a0dd56` / later — current p50 may be stale.

**LATENCY: NEEDS OPTIMIZATION** (not MAJOR GAP vs 30–60s, but not ChatGPT TTFT).

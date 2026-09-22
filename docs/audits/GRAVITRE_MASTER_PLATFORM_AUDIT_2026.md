# GRAVITRE — MASTER PLATFORM AUDIT 2026

**Disposition:** AUDIT ONLY. No implementation. No Gravitre 3.0 start. No Computer Use build.  
**Captured:** 2026-09-22  
**Auditor role:** Principal engineer / AI systems architecture review  
**Default:** PRESERVE unless evidence supports OPTIMIZE / EXTEND / CONVERGE / REPLACE / DEPRECATE / REMOVE.

Evidence legend: **PRODUCTION VERIFIED** · **LIVE TEST VERIFIED** · **INTEGRATION VERIFIED** · **UNIT VERIFIED** · **CODE INSPECTED** · **INFERRED** · **UNKNOWN**.

---

## 1. Primary answer

**If Gravitre were fully understood today, how should its systems operate together — and what prevents that?**

Gravitre is already closer to **one intelligence with multiple interfaces** than to a greenfield product suite. The canonical chat/voice path is:

`User → web/desktop/mobile/voice → POST /api/assistant/chat or WS /api/voice/pipecat/ws → AgentIntelligence.execute_task_streaming → (optional Intent Gateway) → CognitiveTurnKernel ACT pipeline OR classical ReAct → ActionSpec + HMAC/preflight + PendingAction → Observations → Response Composer → SSE or spoken PCM`.

What prevents it from behaving as **one coherent business OS**:

1. **Deploy SHA split** — `origin/main` `5213d3dd` ≠ Railway `a7a0dd56` ≠ Vercel production `a5f97faa`. Operators cannot treat “main” as “what customers run.” (**PRODUCTION VERIFIED**)
2. **Dual tool runtimes** — Unified LIVE is on in production (`unified_turn_live_enabled=true`) while classical ReAct remains the fallthrough. Prior 3.0-B work recorded ~48% fallthrough. LIVE and ReAct are wrappers around the same ActionSpec/HMAC layer, not two products — but semantic/tool-selection truth still diverges. (**PRODUCTION VERIFIED** flags; **LIVE TEST VERIFIED** fallthrough note; not re-measured this hour)
3. **Workflows and Intelligence UI** sit beside the chat kernel. Workflows execute through `execution_engine_runtime.py` without Response Composer. Intelligence pages visualize graph/outcomes without owning execution. (**CODE INSPECTED**)
4. **Objective completion is connector-auth bound.** Isolated org `f07e57c0-…` proves `pending_auth` correctly, not GA4+GSC+HubSpot+Ads completion. Catalog size (~731 unique / ~755 registered actions) is not business-objective coverage. (**LIVE TEST VERIFIED** / **CODE INSPECTED**)
5. **Voice shares the brain, not the full UX.** `spoken_mode=True` hits the same `execute_task_streaming`. HTTP Talk hold and SAPI PCM STT are live-proven. Physical mic, WebRTC, and Lane B production audio remain blocked or denied by design (`production_allows_webrtc_media()==false`). (**LIVE TEST VERIFIED** / **CODE INSPECTED**)
6. **Latency of the live tool path is not ChatGPT-class.** UNIFIED_LIVE_RESOLVED p50 ~13.8s (24h, health SHA `7a2eaaab`). Composer can dominate when it wins the stage. (**LIVE TEST VERIFIED**)

**Verdict:** **PARTIAL single intelligence core** — one ingress and one governance fabric; two live reasoning engines; adjacent workflow/intelligence surfaces; SHA and OAuth gaps hide whether the OS can finish real work.

---

## 2. Current truth (do not infer prod from code)

| Fact | Value | Evidence |
|------|--------|----------|
| Local / origin/main | `5213d3dd` `feat(nav): Nav B prod markers…` | git |
| Production backend | Railway `https://api.gravitre.app` SHA **`a7a0dd56`** @ `2026-09-22T03:03:22Z` status ok | `/health` |
| Production frontend | Vercel `gravitre-saas-backend` latest listed prod **`a5f97faa`** `dpl_73ryW1MTFym3T7N35vnevDhvYCRD` | Vercel API |
| LIVE flags (prod) | `unified_turn_live_enabled=true`, shadow true, embedding tool retrieval true, min catalog 40, task model **low**, QA hooks true, internet research true | `/health` |
| Code default LIVE | `UNIFIED_TURN_LIVE_ENABLED=false` | `config.py` |
| DB / cache | Postgres healthy, Redis healthy | `/health` |
| Temporal / ClickHouse | **configured** | `/health` |
| Isolated org | `f07e57c0-1501-4000-8000-c04e57a00001` | standing rule |
| Operator org | never use `cbbf993b-…` | standing rule |

**Feature flags vs runtime:** Settings defaults are **not** production. Prod health is the runtime source of truth.

**3.0 excluding human (context, not this audit’s job):** D checkpoint live PASS (`c2e362ec-…` / plan `a8d95f75-…`); PCM STT PASS on `c7d6b115`; OAuth/mic/Lane B **EXTERNALLY BLOCKED**. This audit does **not** claim PROGRAM COMPLETE including humans.

---

## 3–4. Architecture map and one-core audit

See `GRAVITRE_CURRENT_SYSTEM_MAP.md`.

Authoritative vs overlapping:

| Component | Role | Disposition |
|-----------|------|-------------|
| `execute_task_streaming` | Only chat/voice turn ingress | **KEEP** |
| Intent Gateway | Shortcuts (connector_status, spoken hold) | **KEEP / OPTIMIZE** |
| CognitiveTurnKernel | Ordered ACT when enabled | **KEEP** |
| Unified LIVE | Tool-calling path, prod on | **CONVERGE** (own fallthrough) |
| Classical ReAct | Fallthrough + non-LIVE | **CONVERGE** then shrink |
| ActionSpec + HMAC + PendingAction | Governance | **KEEP** |
| ContextCompiler | Pack, not always shrink | **OPTIMIZE** |
| Response Composer | Semantic render; extra LLM | **OPTIMIZE** |
| Workflow engine | Parallel executor | **CONVERGE** observations |
| Intelligence UI | Display | **KEEP** (not a brain) |
| Knowledge Fabric | RAG/docs | **OPTIMIZE** consumption |
| Entity fabric | Exact HMAC mentions | **KEEP** |
| Outcome events | Signals | **OPTIMIZE** planner use |
| Pipecat+Deepgram+ElevenLabs | Voice I/O | **KEEP** pending hybrid eval |
| Playwright interact | Flag off | **EXTEND** later, same plan |
| Second planner / memory / voice runtime | — | **DO NOT ADD** |

Semantic truth diverges where LIVE vs ReAct choose tools; execution truth converges on HMAC; memory truth is split across conversation_state, durable_checkpoint, RAG, entities, outcomes; task state diverges if workflows do not stamp the same durable_checkpoint.

Voice vs text: same kernel when `spoken_mode`; Composer + hold_commit + shorter spoken prompts are the intended fork — **not** a second brain. Hidden forks: WebRTC denied; HTTP Talk vs Pipecat WS; empty spoken compose on some PCM samples.

---

## 5–6. Tracing and latency

This audit **did not** re-instrument greeting / general knowledge / WRITE / long-running / error-recovery waterfalls. Unmeasured classes: **UNKNOWN**.

Measured artifacts:

| Class | Result | Level |
|-------|--------|-------|
| Voice HTTP Talk A `voice.turn.operator_first_audio_ms` | p50 **254** / p95 300 (n=5, `2026-09-21T21:25:48Z`) | LIVE |
| Voice HTTP Talk B `voice.turn.operator_completion_ms` | p50 **1832** / p95 2432 | LIVE |
| PCM STT | transcript `is Apollo connected.` session_ready true | LIVE |
| Text turn_total 24h isolated | p50 **13215** / p95 23846 (n=34, Sep 18–19) | LIVE |
| UNIFIED_LIVE_RESOLVED | p50 **13800** / p95 33686, win_count 75 | LIVE |
| Composer when dominant | p50 **18724** (n=5 wins) | LIVE |
| Visible tools p95 | **20** (JIT; not 700-dump) | LIVE |

**Ranked latency contributors (measured impact):**

1. UNIFIED_LIVE_RESOLVED (~13.8s p50) — model + tools serial  
2. COMPOSER extra LLM when it wins  
3. UNDERSTANDING (~2.4s p50 on JIT cohort)  
4. Voice Metric B completion (~1.8s HTTP path)  
5. Tool discovery keyword ~0ms (not the tax)

**Safe parallelization (CODE INSPECTED, savings UNKNOWN):** independent READs; retrieval vs connector status; STT final vs speculative context load. **Must stay serial:** WRITE after approval, HMAC, parameter provenance, spoken hold_commit, dependent tool args.

Full numbers: `gravitre-latency-traces.json`, `GRAVITRE_LATENCY_AND_EFFICIENCY_AUDIT.md`.

---

## 7–10. Models, 2026 review, routing, prompts

See `GRAVITRE_MODEL_AND_TECHNOLOGY_REVIEW.md` and `gravitre-model-call-inventory.json`.

**Prod actually routes assistant tools at tier `low`** (`unified_turn_task_model_tier=low` on `/health`) → **gpt-5.4-mini** on OpenAI preferred. That is a first-order explanation for ChatGPT/Claude quality gap — **INFERRED** from flags + MODEL_TIERS, not a side-by-side eval this pass.

Average prompt/completion tokens, cache hit rate, stable prefix %: **UNKNOWN** (no payload dump this audit). ContextCompiler **reorganizes** and JIT-narrows tools (visible p95=20); whether it **reduces** business context is **CODE INSPECTED / unquantified**.

---

## 11–15. Connectors, autonomy, computer-use, conversation quality

Actions registered ~755 / unique ~731 (**CODE INSPECTED**). F1 HMAC 12 READ + 4 WRITE. Live-proven **business objectives** on isolated org: **PARTIAL** (Apollo pending_auth, retrieve_plan_gate pending WRITE, not HubSpot/Ads/GA4 completed).

Stops at “here is what I would do” when: OAuth pending_auth, WRITE staged PendingAction, or LIVE fallthrough + Composer narrative without tool success.

Computer/browser: **httpx READ present**; Playwright **interact flag default false**. No visible cloud-desktop product. Architecture fit: add an **execution strategy** under the same ExecutionPlan / Observation / PendingAction — **not** a browser brain.

Conversation quality vs ChatGPT/Claude: **PARTIAL / WEAK on latency and model tier**; architecture of follow-ups (spoken hold, task state, STA-312 exact match) is **CODE INSPECTED** and stricter than fuzzy assistants. No fresh qualitative conversation corpus this audit (**UNKNOWN** on ellipsis/pronouns in prod).

---

## 16–20. Voice

See `GRAVITRE_VOICE_PARITY_AND_REALTIME_AUDIT.md`.

Cascade **Pipecat → Deepgram Flux → One Brain → ElevenLabs PCM** is **LIVE** for WS JSON PCM16. Native realtime speech models are **worth evaluating**, not replacing this week. Voice parity: **PARTIAL**. Naturalness: **PARTIAL** (HTTP SLO good; barge-in/WebRTC/mic **UNKNOWN** / blocked).

---

## 21–26. ML, learning, knowledge, memory

See `GRAVITRE_LEARNING_INTELLIGENCE_AUDIT.md`.

Most “intelligence” is **LLM + heuristics + embeddings**, not trained business models. Outcome events persist; planner consumption is weak. Knowledge Fabric is **displayed and optionally retrieved**, not the driver of every tool turn. Long-task memory: durable_checkpoint **LIVE proven** after 3.0-D; full conversation replay still occurs on many turns (**CODE INSPECTED**).

---

## 27–32. Reasoning, tools, parallelism, recovery, governance, observability

- Reasoning/verification: critic/QA hooks **enabled in prod**; causal-claim quality **UNKNOWN** without CEO-scenario live data.  
- Tool discovery: embedding JIT + catalog min 40 **PRODUCTION**; dump invariant tests **UNIT**.  
- Recovery: bounded retries exist; loops **CODE INSPECTED** not quantified.  
- Governance: HMAC + write_allowed + PendingAction on chat path. Workflows must not grow a bypass — **watch**. Browser interact would need the same preflight.  
- Observability: stages exist (UNIFIED_LIVE_RESOLVED, COMPOSER, voice.turn.*). **One trace answering understand→plan→tool→observe→compose→learn** is **PARTIAL** — learn and “why this tool” are not always on the same span.

---

## 33–35. UX cohesion and benchmarks

Surfaces: chat, voice, agents, workflows, Intelligence, reports, desktop, mobile, helper window. Shared task state **intended** via conversation_state / durable_checkpoint; **cross-surface resume** (car → desktop → mobile approve) **UNKNOWN** as a live product test.

Realistic CEO/sales/marketing/finance/ops benchmarks: **BLOCKED** on OAuth or **UNKNOWN**. Do not upgrade to COMPLETED. See `GRAVITRE_CAPABILITY_GAP_MATRIX.md`.

---

## 36–39. Duplication, stack, cost, scale

Duplication: LIVE vs ReAct; multiple context builders historically; workflow vs chat; Pinecone driver vs pgvector primary; HTTP Talk vs Pipecat. Dead second brains: **do not add**.

Stack 2026: Next/Vercel + FastAPI/Railway + Postgres/pgvector + Redis + Temporal + ClickHouse + Pipecat is **defensible**. Change only with measured value (model tier, optional realtime speech, browser provider). No fashion churn.

Cost per task: **UNKNOWN** (no billing export this pass). Dominant cost **INFERRED**: live tool LLM seconds + Composer + ElevenLabs.

Scale: Temporal/ClickHouse configured; horizontal voice WS state **CODE INSPECTED** risk; hundreds of connectors = token risk mitigated by JIT not by dumping.

---

## 40. Questions we had not asked

1. **Three-SHA production** — who owns “what is prod” when git, Railway, and Vercel disagree?  
2. **Settings default false vs health true** — can a local engineer debug the opposite of customers?  
3. **Does LIVE fallthrough still ~48% on `a7a0dd56`?** Not remeasured.  
4. **Tenant-poisoning of outcome learning** if API success is labeled wins.  
5. **Data lifecycle** of PCM, transcripts, rag_embeddings, ClickHouse — retention vs voice in car.  
6. **Helper window / desktop** using a stale API client vs current ActionSpec.  
7. **ClickHouse configured ≠ queried** by the cognitive loop.  
8. **Fine-tune `gpt-4.1-mini` path** — live or shelfware?  
9. **STA-312 exact match vs user expectation of “Sarah”** — product vs safety.  
10. **Vercel project named `gravitre-saas-backend` hosting frontend** — naming drift for operators.  
11. **Whether Composer spoken empty + HTTP Talk success means two voice qualities.**  
12. **Approval identity:** can a voice-initiated WRITE be approved on mobile with the same PendingAction row? **UNKNOWN.**  
13. **Internet research enabled in prod** — grounding policy vs hallucination of the public web.  
14. **Eval blind spot:** no golden set of 20 business objectives run weekly on isolated org.

---

## 41–44. Competitive gap, target, disposition, sequence

See `GRAVITRE_CAPABILITY_GAP_MATRIX.md`, `GRAVITRE_TARGET_ARCHITECTURE.md`, `gravitre-architecture-disposition.json`, `GRAVITRE_CONVERGENCE_PLAN.md`.

**Recommended approach: PRESERVE + CONVERGE** (not major rearchitecture; not 3.0-as-rebuild).

---

## 45. Uncertainty

Major conclusions that are **UNKNOWN** if not listed PRODUCTION/LIVE: qualitative ChatGPT-parity, cache hit rate, cost/task, CEO benchmark completion %, current LIVE fallthrough %, physical-mic naturalness, cross-surface resume.

---

## 47. Executive assessment (required 1–26)

1. **What it is:** A governed AI work runtime with a real connector fabric, dual live/ReAct tool loops, voice cascade, RAG/entities/outcomes, Temporal+ClickHouse configured — **not** yet a category-defining OS in customer-complete work.  
2. **Strong architecture:** One `execute_task_streaming`, ActionSpec/HMAC, PendingAction, spoken hold, JIT tools, durable_checkpoint, isolated-org discipline.  
3. **Preserve:** Ingress, HMAC, approvals, entity exact-match, Pipecat cascade until SLO-beaten, pgvector, Temporal, ClickHouse.  
4. **Drift:** SHA split; LIVE default vs prod; workflow vs chat; Intelligence UI vs engine.  
5. **Duplication:** LIVE+ReAct; RAG stores; voice HTTP vs WS; context compilers.  
6. **Latency:** UNIFIED_LIVE_RESOLVED + Composer LLM.  
7. **Models:** Prod **low** tier; vision still GPT-4o / Claude 3.5; nano for voice conversational.  
8. **Prompt efficiency:** JIT helps tools; full prompt cache stats UNKNOWN.  
9. **Learning:** Signals persist; weak closed loop.  
10. **Knowledge Fabric:** Partial consumption, not execution driver.  
11. **Text/voice equivalent:** Same kernel; not same UX/SLO/WebRTC.  
12. **Voice naturalness:** Cascade + hold works; interrupt/barge-in/mic unproven.  
13. **Long-running autonomous:** Checkpoint yes; Manus-style visible jobs no.  
14. **Manus gap:** artifacts, parallel subtasks UX, browser, background continuation productized.  
15. **Grok computer gap:** no visible cloud browser/computer strategy wired to ExecutionPlan.  
16. **ChatGPT/Claude gap:** latency, model tier, retrieval/memory depth, conversational eval missing.  
17. **Top 10 priorities:** (1) one prod SHA (2) remeasure LIVE fallthrough (3) OAuth isolated-org so objectives complete (4) Composer cost/latency (5) route high-stakes to medium_high (6) one Observation contract for workflows (7) prompt cache measurement (8) voice barge-in eval (9) weekly business golden set (10) browser strategy as ExecutionPlan strategy — design only.  
18. **Do not rebuild:** HMAC/ActionSpec, execute_task_streaming, CognitiveTurnKernel, PendingAction, pgvector fabric.  
19. **Consolidate:** LIVE+ReAct, context builders, voice HTTP/WS metrics, workflow observations, “intelligence” naming.  
20. **Eval upgrades:** stronger default for hard turns; realtime speech hybrid; vision tier 2026; reranker quality; computer-use vendor as strategy.  
21. **Latency wins:** skip Composer when spoken/text already complete; parallel READs; raise cache; don’t dump tools (already JIT).  
22. **Tech risks:** SHA split, fallthrough, outcome poison, WebRTC/security, browser interact off-HMAC.  
23. **Product risks:** pending_auth as “dumb assistant”; Intelligence page as fake brain; catalog size as vanity.  
24. **Unasked questions:** §40.  
25. **Target:** one core, one task truth, multiple strategies/interfaces — `GRAVITRE_TARGET_ARCHITECTURE.md`.  
26. **Migration order:** integrity (SHA/flags) → reliability (LIVE owns tools) → latency (Composer/parallel READ) → cohesion (workflows) → voice parity → autonomy/computer **design** → learning consumption.

**PLATFORM COHESION:** PARTIAL  
**SINGLE INTELLIGENCE CORE:** PARTIAL  
**TEXT QUALITY:** PARTIAL  
**VOICE PARITY:** PARTIAL  
**VOICE NATURALNESS:** PARTIAL  
**AUTONOMOUS EXECUTION:** PARTIAL  
**BUSINESS MEMORY:** PARTIAL  
**OUTCOME LEARNING:** WEAK  
**COMPUTER / BROWSER EXECUTION:** FOUNDATION ONLY  
**MODEL STACK:** PARTIALLY OUTDATED  
**LATENCY:** NEEDS OPTIMIZATION  
**RECOMMENDED APPROACH:** PRESERVE + CONVERGE

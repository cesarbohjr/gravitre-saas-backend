# GRAVITRE — TARGET ARCHITECTURE

**Audit only.** This is a target **based on what already works**, not a 3.0 rewrite and not a new product.

Evidence: **CODE INSPECTED** + **PRODUCTION VERIFIED** flags. No implementation.

---

## Principles

1. **ONE INTELLIGENCE CORE** — `execute_task_streaming` + CognitiveTurnKernel. Unified LIVE should **own** tool turns; classical ReAct shrinks to compatibility until fallthrough is ~0 on the golden set.  
2. **ONE TASK TRUTH** — `conversation_state` including `durable_checkpoint` / `durable_session`. Every surface (text, voice, mobile approve, workflow child) reads/writes this.  
3. **ONE EXECUTION PLAN** — ExecutionPlan / ActionSpec instances. Browser, API, workflow step, background job are **strategies**, not plans.  
4. **ONE CAPABILITY MODEL** — ontology + resource resolver; vendor quirks behind adapters.  
5. **ONE GOVERNANCE SYSTEM** — HMAC, parameter provenance, PendingAction, tenant isolation. Computer/browser writes use the same PendingAction.  
6. **ONE BUSINESS MEMORY FABRIC** — partition by class of truth (working / semantic / document / entity / outcome). Stop overlaying “brains.”  
7. **ONE OUTCOME LEARNING LOOP** — events already persist; **consume** in planning with tenant isolation and API-success ≠ business-success.  
8. **ONE RESPONSE SEMANTIC LAYER** — Composer renders **the same truth** for text / voice / compact / workspace.  
9. **MULTIPLE EXECUTION STRATEGIES** — API connector, workflow, agent delegation, browser/computer, background job.  
10. **MULTIPLE INTERFACES, ZERO extra brains** — text, voice, desktop, mobile, AI workspace.

---

## What to reuse (PRESERVE)

- AgentIntelligence ingress  
- ActionSpec + F1 HMAC + PendingAction  
- Spoken hold_commit  
- JIT embedding tool retrieval (visible tools p95=20 is the right direction)  
- pgvector Knowledge Fabric  
- Entity HMAC mentions (STA-312)  
- Pipecat + Deepgram + ElevenLabs until a hybrid realtime eval **beats** Metric A/B  
- Redis, Postgres, Temporal, ClickHouse  
- httpx browser READ  

---

## What to converge (not replace)

- Unified LIVE and ReAct → one tool loop  
- Workflow observations → same Observation type as chat  
- HTTP Talk and Pipecat metrics → one voice SLO vocabulary  
- Context builders → ContextCompiler only  
- Intelligence UI copy → “visualization of fabric,” not a second OS  

---

## What to extend later (design, not this audit)

- **Gravitre Computer** as an ExecutionPlan strategy: cloud browser/computer, pause/takeover, Observations of DOM/screenshot hashes, governance identical to WRITE. Provider category: hosted browser/computer-use (evaluate; do not pick in this document as a vendor lock-in).  
- Stronger model **tier for high-stakes** turns only — keep low for greetings/hold.  
- Hybrid realtime speech **beside** cascade, same kernel.  

---

## Explicit non-goals

- No second cognitive runtime  
- No second planner  
- No second memory product  
- No second voice brain  
- No Intelligence-page-defined backend  
- No Gravitre 3.0 rewrite  

---

## Interface contract (target)

A user may:

1. Start a task by voice in a car (`spoken_mode`).  
2. Continue on desktop (same conversation_id / durable_checkpoint).  
3. Inspect entities/outcomes on Intelligence (read-only fabric).  
4. Approve a PendingAction on mobile.  

If any of those four cannot share task identity, the platform is still **PARTIAL**. Live proof of the full loop is **UNKNOWN** today.

---

## Cohesion test (exit criteria for “one OS”)

- One SHA on git, Railway, and Vercel production.  
- LIVE fallthrough below an explicit threshold on the golden set (**UNKNOWN** current %).  
- Workflows emit Observations the Composer can narrate.  
- Voice and text produce the same ExecutionPlan for the same utterance.  
- Browser strategy, if added, never gets its own LLM router.

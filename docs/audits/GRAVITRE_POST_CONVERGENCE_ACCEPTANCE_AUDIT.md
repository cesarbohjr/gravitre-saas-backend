# GRAVITRE POST-CONVERGENCE ACCEPTANCE AUDIT

**Independent of the implementation report.** Claims in the ledger and final implementation report were re-scored against code at `426fce81` and live production on that SHA.

**Date:** 2026-09-22  
**Auditor role:** acceptance, not implementation. No fixes applied.

---

## Deployment truth

| Surface | SHA |
|---------|-----|
| origin/main | `426fce81964dbe27af0300c7a19c73dadca888be` |
| local HEAD | same |
| Railway `GET https://api.gravitre.app/health` | **`426fce81`** @ 2026-09-22T14:16:05Z |
| Vercel production | **`426fce81`** deployment `dpl_7JZq2GLytf6GgtGGpfexFiGZvYxm` READY |
| Required CI (`CI`) | **success** https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35706291861 |
| Railway backend production workflow | success |
| Isolated org | `f07e57c0-1501-4000-8000-c04e57a00001` |
| Flags | LIVE true, shadow true, task tier **low**, `convergence_p1_single_selection_v1` **true** |
| Migrations | UNKNOWN (health `database=healthy` only) |

**`426fce81` is deployed** on backend and frontend. Live tests below are **on the implementation SHA**, not `a7a0dd56`.

Other GitHub jobs on this SHA **failed** (not the required `CI` workflow): Authenticated Click Audit, Voice duplex browser guard, Connector Verified Writes Live, Credential DB Bypass Guard (Daily). Recorded as OPEN P1, not used to invent product PASS.

---

## Verdict vs implementation report

The implementation report said 0 FAILED, 43 IMPLEMENTED_PROOF_PENDING, engineering complete, 0 live verified (because SHA had not deployed yet).

**Independent live re-score on the now-deployed SHA:**

- Several items **FAIL** in production (P1 dual-select, P4 CEO, P3 PCM spoken, P2 waterfall + TTFT, P5 Composer waiting unwired, ledger stale).
- Unit tests **do not** equal intended product behavior.
- Architecture is **PRESERVE + CONVERGE** (no second brain) with **incomplete wiring** of P1/P3/P4/P5.

**CONVERGENCE PROGRAM ACCEPTED: NO**  
**FULL SECTION 0 PRODUCT ACCEPTED: NO**

---

## Architecture conformance

**Preserved:** `execute_task_streaming`, CognitiveTurnKernel, ExecutionPlan, ActionSpec, HMAC/preflight, PendingAction, Composer, KF, entity fabric, durable checkpoint, tenant isolation, governance, sealed READ for “Show my deals.”

**No new parallel intelligence/planner/memory/voice/workflow/learning/Composer system.** P1–P6 are flags + adapters on the existing spine.

**P1 live:** LIVE still performs model tool-selection (`gpt-5.4-mini`, `read_tool_classical`). ReAct then runs `inference.tool_completion` and `agent.react.iteration` on CEO. HubSpot proposal is not executed. HMAC not bypassed. Composer still owns prose. **Second tool-selection path remains. P1 FAIL.**

Likely cause (inspect only): handoff requires `tool_name` on LIVE result; ContextVar + ReAct later iterations still choose KB/status tools. Units only test stash/consume in isolation.

**P3 inspect:** origin is stored on a **ContextVar**. Pipecat processors run on other tasks; live SAPI still emits `speech.interrupted` before a spoken answer. Units pass; production does not.

**P5 inspect:** `workflow.child.observation` exists on linear `execute.py`. Composer kind `workflow_waiting` has **no orchestration call site**.

---

## Phase results (live on 426fce81)

### P0 — NON-REGRESSION — PASS (quality) / FAIL (speed)

Conv `1dfc6b80-…`: `hubspot.deals.list`, 25 deals, canned, HMAC `plan_id` `3dbabd9b-…`, `step_id` `read_sales_pipeline_health`, `provider_invoked` true. Answer: “I found 25 deals in the connected CRM.”  
TTFT **29823 ms** vs baseline **19931 ms** (+49.6%).

### P1 — SINGLE SELECTION — FAIL

CEO conv `c0422a72-…`: LIVE fallthrough `read_tool_classical` then `inference.tool_completion` **twice** and four `agent.react.iteration`. Tools: KB, workflow runs, connector status, agent status. **Not** one semantic selection + one-shot execute.  
Pending-family / defer-SSE **preserved** (24h isolated: defer 38, pending-family 19, read_tool_classical 15).

### P2 — LATENCY — FAIL

Live `runtime.turn_latency.critical_path` meta is `{spoken_mode:false}` only — **no waterfall**. Canned-literal skip exists in Composer when `provider_result_evidence` is present; HubSpot first text did **not** improve. See `gravitre-post-convergence-latency.json`.

### P3 — VOICE — FAIL (PCM) / PASS (HTTP Talk) / HUMAN_TEST_PENDING (mic)

PCM `gravitre-pcm-closure-live.json` @ 426fce81: transcript OK; `assistant_text` empty; `audio_frames` 0; `interrupt_events` 2.  
HTTP Talk greeting: text 237 ms, audio 285 ms.  
`user_mic` barge-in: **unit only**. Physical driving: **HUMAN_TEST_PENDING**. Automated PCM is **not** physical-mic acceptance.

### P4 — BUSINESS EVIDENCE — FAIL

Healthy HubSpot + Google Ads on isolated org. CEO answer did not include a HubSpot or Ads Observation and did not honestly name GA/GSC `pending_auth`. KF/status tools still ran.

### P5 — WORKFLOW SAME TASK — NOT_RUN + code PARTIAL

No chat-started workflow this audit. Composer waiting path unwired.

### P6 — OUTCOMES — PARTIAL

7d n=50: no `business_metric_improved`. TOOL_SUCCESS filtered in unit. Consume of labeled impact **EXTERNALLY_BLOCKED** (H11). Storing rows is not learning.

### M — EXTERNALLY_BLOCKED

No local eval key. Prod default still `low`. Not inferred.

### P7 freeze — PASS

No Computer Use / second brain.

---

## Product experience (Section 0)

| Dimension | Rating | Evidence |
|-----------|--------|----------|
| Text | PARTIAL | Greetings and CRM count work; CEO copy is a failed-compile message; 20–30s waits. |
| Voice semantic parity | PARTIAL | HTTP Talk shares kernel; Pipecat PCM does not complete spoken delivery. |
| Voice natural / driving | HUMAN_TEST_PENDING | Physical mic not run; PCM FAIL. |
| Autonomous execution | DOES_NOT_MEET | Deals count is completed READ; CEO/ops objective not executed. |
| READ | MEETS | HubSpot list HMAC. |
| WRITE | MEETS | Sarah clarify; no silent send. |
| Artifacts | DOES_NOT_MEET vs vision / exception vs program | Deferred factory; description ≠ file. |
| Continuity | DOES_NOT_MEET | EV-J-007/008 NOT_RUN. |
| Business evidence reasoning | DOES_NOT_MEET | P4 live FAIL. |
| Outcome learning | DOES_NOT_MEET | No impact consume. |
| Latency | DOES_NOT_MEET | HubSpot +49.6%; greetings slower. |
| Architecture convergence | PARTIAL | Spine preserved; P1/P3/P4 adapters ineffective live. |
| Governance | MEETS | Isolated org; no WRITE bypass; HMAC on deals. |

---

## Observability gaps

A single CEO task **cannot** currently answer from `runtime.turn_latency.critical_path` what understanding/preflight/provider/compose/first_sse cost. LIVE breakdown exists on fallthrough meta only. P2 contract marks are not in the live audit payload.

---

## Machine files

- `gravitre-post-convergence-requirement-results.json` (56 IDs, independent statuses)
- `gravitre-post-convergence-journeys.json`
- `gravitre-post-convergence-latency.json`
- `gravitre-post-convergence-regressions.json`
- `GRAVITRE_POST_CONVERGENCE_GAP_PLAN.md` (recommendations only)

Live sources: `gravitre-evidence-closure-live.json`, `gravitre-pcm-closure-live.json` (both SHA `426fce81`).

---

## Final scorecard (section 25)

```
IMPLEMENTATION SHA: 426fce81964dbe27af0300c7a19c73dadca888be
DEPLOYED BACKEND SHA: 426fce81 (Railway health 2026-09-22T14:16:05Z)
DEPLOYED FRONTEND SHA: 426fce81 (Vercel dpl_7JZq2GLytf6GgtGGpfexFiGZvYxm)
REQUIRED CI: PASS CI run 35706291861
56 REQUIREMENTS:
PASS: 22
PARTIAL: 12
FAIL: 13
NOT_RUN: 5
EXTERNALLY_BLOCKED: 2
SCOPE_EXCEPTION: 2
P0: PASS (HubSpot 25 HMAC/grounding) / FAIL (TTFT +49.6%)
P1: FAIL (LIVE + ReAct dual tool-selection on CEO)
P2: FAIL (waterfall absent live; HubSpot/Sarah slower)
P3: FAIL (SAPI PCM empty assistant, 2 interrupts) / PASS (HTTP Talk 237/285ms) / HUMAN_TEST_PENDING (physical mic)
P4: FAIL (CEO used internals; skipped healthy HubSpot/Ads)
P5: NOT_RUN live; PARTIAL code (workflow_waiting unwired)
P6: PARTIAL (TOOL_SUCCESS gated in unit; no BUSINESS_IMPACT consume)
M: EXTERNALLY_BLOCKED
P7 FREEZE: PASS
TEXT EXPERIENCE: PARTIAL
VOICE SEMANTIC PARITY: PARTIAL
VOICE NATURAL EXPERIENCE: HUMAN_TEST_PENDING
AUTONOMOUS EXECUTION: DOES_NOT_MEET
READ EXECUTION: MEETS
WRITE EXECUTION: MEETS
OUTPUT / ARTIFACT PRODUCTIVITY: DOES_NOT_MEET
TASK CONTINUITY: DOES_NOT_MEET
BUSINESS EVIDENCE REASONING: DOES_NOT_MEET
OUTCOME LEARNING: DOES_NOT_MEET
LATENCY: DOES_NOT_MEET
ARCHITECTURE CONVERGENCE: PARTIAL
GOVERNANCE: MEETS
OPEN P0: P1 dual-select; P3 false barge-in / silent PCM; P4 CEO evidence; P0 HubSpot first-text regression
OPEN P1: P2 waterfall+TTFT; P5 Composer waiting; ledger stale; four non-required CI jobs failed; P6 consume; M keys
EXTERNAL BLOCKERS: M eval key (H7); P6 labeled impact (H11)
CONVERGENCE PROGRAM ACCEPTED: NO
FULL SECTION 0 PRODUCT ACCEPTED: NO
READY FOR NEXT PRODUCT PHASE: NO
```

No product fixes were applied in this audit. Gap plan is recommendations only. Stopped for Cesar's review.

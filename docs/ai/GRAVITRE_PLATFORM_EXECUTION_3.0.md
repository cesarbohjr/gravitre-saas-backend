# Gravitre Platform Execution 3.0 — specification

**Status:** 3.0-A CLOSEOUT + 3.0-C IN PROGRESS (2026-09-19). Production voice remains cascade lane A (JSON PCM16 WebSocket). Native realtime (lane B) and WebRTC media are eval-only.  
**Date:** 2026-09-18  
**Product target:** one Intelligence Core that can take natural intent (text or voice), classify work vs chat, acknowledge quickly, compile only needed context, execute safely, recover, deliver finished business output, and learn from outcomes — without cloning Manus, Claude Cowork, or ChatGPT private runtimes, and without a second Gravitre brain.

No customer-facing prices, Certified/TRAINED badges, or Enable toggles. Certification remains process Track A/B/C unless product separately authorizes UX.

---

## Research principles

1. **One Intelligence Core.** Text, voice, desktop, workflows, and agents are surfaces over the same E1–E5 / F1 / Composer / governance stack.
2. **Quality before autonomy.** Do not add Cowork-length loops or native-realtime model swap while competing compile cores and unmeasured latency remain.
3. **Interaction loop ≠ work loop, same truth.** Progress speech may start before evidence; success speech may not.
4. **Compile before strategy.** `compiled_task` stays **OPTIONAL_PROJECTION** (2.0 A0). ExecutionPlan + PreflightResult + ContextCompiler remain SoT. Do not mint a second BusinessTask runtime.
5. **WRITE stays gated.** F1 HMAC, `react_write_gate`, canvas write authority, and G8 are not bargained for latency or voice naturalness.
6. **Memory Phase 1 stays exact HMAC** of normalized mentions — not fuzzy `"Sarah"`↔`"Sarah Smith"`. Entity joins need a named PII owner (STA-312 class). Schema-gate ≠ authorization.
7. **Public product behaviors, not private architecture.** Adapt *what users experience* (fast ack, barge-in, durable tasks, artifacts). Do not import vendor internals.
8. **Evidence-linked PASS.** UNIT_TEST ≠ LIVE_USER_PROVEN. Voice Metric A and Metric B stay separate ([voice-slo-two-metric-standard](../delivery/voice-slo-two-metric-standard-2026-09-11.md)).
9. **No metric may silently degrade another.** Accuracy, autonomy, latency, concision, context quality, execution success, voice naturalness, safety, recoverability, observability.

---

## 3.0-C progress (2026-09-19)

Append-only. Does not replace 3.0-A closeout or retire LIVE_USER_PROVEN gaps.

- Spoken Metric A/B samples: HTTP Talk probe `scripts/verify-voice-slo-two-metric-live.py` → `docs/delivery/voice-slo-two-metric-live.json` captured `2026-09-19T07:53:33Z` against `/health` SHA `653303a3…` org `f07e57c0-…`. Metric A samples ms `[1166, 375, 392, 318, 340]` P50 **375** / P95 **1166** — P50 under 500ms, P95 over 800ms (**FAIL** on the two-number A bar). Metric B `[26989, 53054, 22849, 8719, 30029]` P50 **26989** / P95 **53054** vs 5s/8s (**FAIL**). A and B stay separate; blending forbidden. Conversations include `5317f08c-a36b-427e-be04-a3d4ca699265`.
- Pipecat path now records Metric B on `AssistantStreamComplete` for operator/tool turns (`voice.slo.metric_b`, source `pipecat_composed_final`). Metric A remains duplex first-speech.
- **TTS context cancel:** barge-in calls ElevenLabs `close_context` and **keeps** the session WebSocket (`voice.tts.context_cancelled`). Not a session teardown / InterruptibleTTS reconnect.
- **WebRTC eval:** `voice_webrtc_eval.py` measures startup / media RTT / jitter / loss / reconnect / region. `production_allows_webrtc_media() == false`. Production transport remains `websocket_pcm16_json`.
- Lane B still must not serve live customer audio.
- **Barge-in WRITE safety (3.0-C):** TRUE_INTERRUPT / `/api/voice/session/cancel` / HTTP Talk turn cancel arms conversation stop (`voice.barge_in.write_gate`). ReAct refreshes the interrupt at WRITE execute time so an uncommitted write is `write_commit_interrupted` (`provider_invoked=false`). READs are not speculative-cancelled by this gate.
- **ASR catalog lexicon:** Deepgram keyterms add a bounded set of connected-vendor **READ** ActionSpec names (no employee personal names).

---

## 2.0 audit ingestion

### Files requested vs files that exist

| Prompt path | In repo? | Used as |
|-------------|----------|---------|
| `docs/delivery/GRAVITRE_PLATFORM_EXECUTION_2.0_FINAL_AUDIT.md` | **Missing** | Substituted [gravitre-autonomous-execution-reaudit-2.0.md](../delivery/gravitre-autonomous-execution-reaudit-2.0.md) (2026-09-18 **CODE + UNIT_TEST + `/health`**, explicitly **not LIVE_USER_PROVEN**) |
| `docs/delivery/gravitre-2.0-requirement-ledger.json` | **Missing** | Substituted 2.0 spec work-item map + re-audit COMMON_SENSE_GAP CS-1–15 + Part 46 priority map |
| `docs/ai/GRAVITRE_PLATFORM_EXECUTION_2.0.md` | **Present** | Binding 2.0 architecture; A0 corrections are **not** optional |

Also ingested (supporting, not a replacement audit): voice two-metric SLO, older `text-voice-task-execution-parity-live.json` (SHA `4185a00b`, orchestration-plan parity — **not** F1/SC live traffic, **not** barge-in).

### Audit snapshot (do not treat as today’s tip)

Re-audit baseline: local/`origin` `dcc2324b`; prod `/health` `f4accdfc` @ 2026-09-18T06:28:02Z; merge CI **red**; golden live smoke JSON **missing**.

Primary finding: **compiler island on a thin F1 READ slice + analytics short-circuit; majority of work is still a NL router (ReAct / model args).** Manus-like operator: **PARTIAL**.

### Subsequent `main` (source, not live-proven here)

After the re-audit, later commits on `main` (including 2.0-A–H cohesion, HMAC READ expansion, ExecutionPlan follow-up continuity `09b907ef`, UX Reset 2.0) **changed source**. They do **not** retire the re-audit’s LIVE_USER_PROVEN gaps. 3.0 must treat:

| Claim | 3.0 stance |
|-------|------------|
| F1 HMAC + ActionSpec Option B | **REUSE** — do not rebuild |
| Analytics SC as second compiler | **CONVERGE** into same preflight (2.0-A unfinished as LIVE_PROVEN) |
| `compiled_task` as SoT / ingress gate | **REJECTED** (2.0 A0) |
| WRITE auto-HMAC / auto-approve | **FORBIDDEN** |
| Voice = same kernel | **REUSE STRUCTURAL**; semantic/latency **NOT_PROVEN** |
| CS-7 task continuity | **EXTEND** ExecutionPlan `plan_id` (2.0-H in source; live **NOT_PROVEN**) |
| Entity join CRM=QBO=Zendesk | Still **NEW_REQUIRED** |
| Causal multi-source “why pipeline” | Still **NEW_REQUIRED** on E5 |
| F2 one-shot | **EXTEND** to classed budget |
| Companion `run_ga4_report` HMAC | **CONVERGE** if still bypassed |

### 2.0 blockers that must close before 3.0 product loops

These are **program blockers**, not optional polish:

1. **LIVE_USER_PROVEN F1/SC traffic turn** with `conversation_id` + `audit_events` + `/health` SHA match (2.0-A0). Isolated-org golden smoke artifact still required.
2. **Invariant I:** operational compile **before** ReAct `tool_choice` / LIVE strategy; SC companions on same HMAC; Composer-only user prose (no `Stopped.` SSE).
3. **Do not weaken** WRITE/`react_write_gate`/HMAC/G8 while adding voice or durable work.
4. **CI honesty:** standing-red named or fixed before claiming a 3.0 phase Done.
5. **Voice stages unmeasured** on current tip: speech_end → first audible PCM (Metric A) vs completion (Metric B); barge-in near WRITE; text↔voice **IDs** not just similar copy.
6. **STA-312 / Memory Option B:** no fuzzy person join; entity fabric needs named owner before cross-system customer identity.

Until (1)–(3) hold, 3.0-C native realtime evaluation and 3.0-D long-running Cowork sessions stay **gated**. Measurement and cohesion may start.

---

## Classification key (3.0)

| Label | Meaning |
|-------|---------|
| **REUSE** | Healthy E1–E5/F1/2.0 owner — do not rebuild |
| **EXTEND** | Grow the existing type/service |
| **CONVERGE** | Multiple paths; fold into one owner |
| **REPLACE** | Stop treating as SoT (adapter until cutover) |
| **NEW_REQUIRED** | Missing layer; add only if existing types cannot represent it |
| **DEFER** | After reactive + measured baseline |

---

## Every proposed 3.0 capability — classification

| § | Capability | Class | Existing equivalent | Notes |
|---|------------|-------|---------------------|-------|
| 2 | One Intelligence Core | **REUSE** | `execute_task_streaming`, kernel, Composer | No VoiceBrain / CoworkBrain / ManusRuntime |
| 3 | Interaction vs work loop | **EXTEND** | Composer `kind=progress` vs final; STA-343 narration | Same `task_id` / plan / entities / permissions |
| 4 | Task classifier / budget | **EXTEND** | Intent Gateway (chitchat only); capability router; SC flag | Deterministic/cheap; **not** business SoT |
| 5 | Fast acknowledgement | **EXTEND** | Composer progress; voice Metric A | Structured PROGRESS; never fake result |
| 6 | Progressive commitment | **EXTEND** | E1 resolution + resource cache | No irreversible WRITE from incomplete speech |
| 7–9 | Semantic turn / adaptive endpoint / backchannel | **NEW_REQUIRED** (voice media) | Fixed VAD/silence; interrupt primitives | Must not fork execution compiler |
| 10 | Barge-in 3.0 | **EXTEND** | `AgentExecutionInterrupted`; invoke interrupt | WRITE-near special case; Stop = deterministic |
| 11 | Voice corrections | **EXTEND** | E5 plan + reference resolver (2.0-H) | Edit structured state; don’t mint unrelated task |
| 12 | Business-aware ASR repair | **EXTEND** | Tenant identity / catalog lexicon | Confirm uncertain WRITE identity |
| 13 | Voice persona / output budget | **EXTEND** | Composer `spoken_mode` | Same facts; different render |
| 14–15 | Native realtime + WebRTC eval | **NEW_REQUIRED** (eval lane only) | Deepgram → kernel → ElevenLabs | No prod swap without benchmark |
| 16–21 | Audio preprocess, STT/TTS stream, warmth | **EXTEND** | Pipecat, TTS chunking, sockets | First-audio, not API RTT alone |
| 22–25 | Latency SLOs, full trace, critical path, regression | **EXTEND** | Two-metric SLO; Flux internals “not the SLO” | Per-task budgets; fail unnecessary delay |
| 26–29 | JIT context, scoring, cache, compaction | **EXTEND** | E4 ContextCompiler; compiled_task projection | Smallest high-value context |
| 30–32 | JIT tools, search, examples | **EXTEND** | execute-now attach; 732 catalog; F1 eligible set | Never dump 700 tools |
| 33–35 | Programmatic orch, bounded results, pagination | **EXTEND** | Adapters, NormalizedResult | Code does mechanics |
| 36–37 | Smart READ composites, overlap | **EXTEND** | Capability recipes | No hidden WRITE in composites |
| 38–40 | Model routing, reasoning budget, early exit | **EXTEND** | F1 no-model params; `unified_turn_task_model_tier` | Measure first (2.0) |
| 41–42 | Evidence reasoning, confidence labels | **EXTEND** | Composer honesty; outcome labels | FACT/INFERENCE/HYPOTHESIS/RECOMMENDATION |
| 43–46 | Join planner, parallel READ, speculative READ, fallback | **NEW_REQUIRED** / **EXTEND** | Domain bind; GA4+GSC recipe; F2 sibling | Joins need BusinessEntity; no speculative WRITE |
| 47–48 | Repair 3.0, error memory | **EXTEND** | F2 one-shot | In-task only; no learning transient 4xx as facts |
| 49–56 | Durable work, background, checkpoint, takeover, artifacts, deliverable, stop, verify | **EXTEND** E5 | Plan states; pending_task compatibility | Map onto E5; don’t replace |
| 57–59 | Skills / procedures / versioning | **EXTEND** | Packs, knowledge, recipes | Not a second agent runtime |
| 60–61 | Contained execution, permission boundaries | **DEFER** / **REUSE** | Tenant + connector scopes | Sandbox later; don’t destroy task on sandbox fail |
| 62 | Approval fatigue | **REUSE** | READ auto if authorized; WRITE risk-based | |
| 63–64 | Prompt-injection, provenance | **EXTEND** | Untrusted retrieval; Observation | External content ≠ instructions |
| 65–67 | Voice WRITE safety, spoken approval, yes-wait | **EXTEND** | PendingAction; interrupt | Atomic commit boundary traced |
| 68–69 | Text↔voice, multi-device | **EXTEND** | Same `execute_task_streaming` | Media ephemeral; task persistent |
| 70–72 | Progress, concise answers, channel Composer | **EXTEND** | Composer SoT | One semantic object |
| 73–74 | Proactive, attention | **DEFER** | Health jobs | 2.0-M; no invented alert SKUs |
| 75–85 | Eval suites, shadow, canary, goldens, adversarial | **EXTEND** | Goldens A–G; voice SLO gates | Shadow: no duplicate WRITEs |
| 86–88 | Observability, no CoT dump, cost | **EXTEND** | E2 | Structured decisions |
| 89 | No-regression | **POLICY** | This document | Previous golden suite every phase |

---

## Target architecture (one harness)

```
INGRESS (text / voice STT / agent-scoped chat / workflow invoke)
  → INTERACTION LOOP (ack, clarify, progress, barge-in, corrections)
       shares IDs with
  → WORK LOOP
       E1 resolve (intent, capability, time, entities)
       E5 ExecutionPlan shell (lineage; not FM planning)
       kernel pre-act (retrieve; heuristic PLAN ≠ exec SoT)
       TASK CLASS / BUDGET (cheap; not truth)
       E4 ContextCompiler  **required before FM / ReAct**
       JIT tool namespace (eligible ActionSpecs only)
       strategy: NO_MODEL | FAST | ReAct | LIVE | workflow | durable session
       F1 HMAC preflight (priority READs) → invoke_tool → Observation
       WRITE: compile facts → policy → PendingAction → execute → verify
       F2/3.0 repair (bounded)
       Composer (one semantic result → TEXT / VOICE / PROGRESS / APPROVAL / ARTIFACT)
       E2 trace
```

**Forbidden:** VoiceBrain, CoworkBrain, ManusRuntime, second connector executor, `compiled_task` as gate, speculative WRITE, success before Observation.

---

## Interaction loop vs work loop

| | Interaction | Work |
|--|-------------|------|
| Optimize | Turn-taking, Metric A, barge-in | Objective completion, Metric B / text final |
| May | Ack, clarify, progress, interrupt handling | Plan, READ, WRITE (gated), repair, artifacts |
| Must not | Declare success, invent numbers, skip HMAC/approval | Speak raw CoT, dump 5k CRM rows to TTS |
| Shared | `conversation_id`, `task_id`/`plan_id`, entities, permissions, outcomes | same |

E5 state mapping (prefer existing names; add aliases only if missing):

`CREATED` → `UNDERSTANDING` → `PLANNING` → `WORKING` → `WAITING_USER` | `WAITING_APPROVAL` | `WAITING_EXTERNAL` → `REPAIRING` → `VERIFYING` → `COMPLETED` | `PARTIAL` | `FAILED` | `CANCELLED`.

---

## Voice architecture

**Current cascade (production candidate A):** Deepgram STT → `voice_session_service` / Pipecat → `execute_task_streaming(spoken_mode=True)` → Composer → ElevenLabs TTS.

**Must preserve:** same kernel as text; STA-343 progress speech; two-metric SLO; interrupt near WRITE; no speculative WRITE.

**3.0 media additions (interaction loop only):** semantic turn detector, adaptive endpointing, backchannel vs TRUE_INTERRUPT, ASR lexicon from tenant identity/catalog, independent TTS context cancel, connection warmth with idle expiry.

**Spoken approval:** “Send this to Sarah Khan now?” bound to exact `PendingAction`. “yes—wait” before commit cancels. Trace the atomic boundary.

### Voice benchmark architecture (no production replacement without evidence)

| Lane | Path | Allowed in prod? |
|------|------|------------------|
| **A CURRENT CASCADE** | STT → canonical runtime → TTS | **Yes** (today) |
| **B NATIVE REALTIME** | Speech/audio model → **same** Gravitre runtime for tools → audio | Eval / shadow only |
| **C HYBRID** | Realtime conversation frontend + deterministic tool/work backend | Eval; likely 3.0-C recommendation if B fails governance/trace |

Benchmark: semantic accuracy, interruptions, tool correctness, latency (A and B separate), cost, naturalness, traceability, governance, context parity. WebRTC: startup, media RTT, jitter, loss, reconnect, region — **not** model TTFT alone.

Older parity JSON (`4185a00b`) proved **orchestration copy** match on Ads plan — **not** F1 HMAC traffic, **not** barge-in, **not** current SHA.

---

## Latency architecture

Do **not** one SLO for all tasks. Keep Metric A / Metric B for voice. Add text/work clocks:

| Class | Clock | Directional budget (set numbers after 3.0-A baseline) |
|-------|-------|------------------------------------------------------|
| VOICE SIMPLE | speech_end → first audible | Metric A: P50 <500ms, P95 <800ms (standing) |
| VOICE READ ack | speech_end → progress audio | Metric A |
| VOICE READ / tools | speech_end → final | Metric B: P50 <5s, P95 <8s (standing) |
| TEXT QUICK | request → first delta | measure then set |
| TEXT READ | request → progress; request → final | measure then set |
| LONG TASK | request → visible work start; cadence; complete | no fake “done” |

**Full trace stages (required):** network ingress, audio buffers, VAD, turn detector, STT partial/final, resolution, ContextCompiler, tool discovery, model queue, TTFT, planning, preflight, provider, repair, synthesis, Composer, TTS queue, TTS first byte, client buffer, first audible PCM.

**Critical path analyzer:** each slow turn tags dominant stage (`STT_ENDPOINTING`, `MODEL_TTFT`, `CONTEXT_BUILD`, `TOOL_DISCOVERY`, `PROVIDER`, `SERIAL_READS`, `TTS_BUFFER`, `NETWORK`). Fail the phase if architecture adds delay without a named trade.

---

## Context architecture (JIT)

E4 stays the compiler. 3.0 adds **value scoring** (relevance, freshness, authority, token cost, task dependency) and **revision-keyed caches** (org identity, ActionSpecs, resource catalogs, stable policy).

Working memory for long tasks: objective, decisions, facts, open questions, plan, observations, artifacts. Compact chatter; never drop decision-critical facts.

Start with identifiers + summaries; retrieve depth on demand. Trace INCLUDE/EXCLUDE (already E4 direction).

---

## Tool discovery and design

732 catalog actions stay in the registry. Models see a **small eligible namespace**: capability + source selection + `CAN_THIS_ACTION_EXECUTE_NOW` + F1/compiled-eligible set.

**Tool search** is a deterministic, tenant-aware catalog query — not an LLM with the whole schema.

ActionSpec **may** carry short usage examples; schemas remain SoT.

Deterministic pagination, join, sort, dedupe, date math run in **code**. High-signal observations: filtered, bounded, with provenance. Large tools: `limit` / cursor / field select / summary.

`get_customer_business_context`-class **READ** composites allowed only if they cannot WRITE and provenance is preserved.

---

## Model routing and reasoning

| Path | When |
|------|------|
| NO_MODEL | Time/resource/params F1; formatters |
| FAST_MODEL | Simple chat, known lookup phrasing |
| STANDARD_REASONING | Typical operational READ/WRITE plan |
| DEEP_REASONING | Conflict, multi-source causal, high-risk plan, replan |

Early exit when deterministic compile already answered. Evidence loop for deep work: question → hypotheses → required evidence → acquire → update → verify → conclusion. Labels: FACT / INFERENCE / HYPOTHESIS / RECOMMENDATION.

---

## Parallelization, repair, durable work

Independent **safe READs** concurrent after join/deps; WRITEs sequential/governed. Speculative READ only if high confidence, cheap, cancellable, no privacy escalation. **Never speculative WRITE.**

Repair 3.0 = classed F2 budget + in-task error memory (action, args, resource, reason). Human takeover resumes **same** `plan_id`.

Durable session: persist plan, context **refs**, resource identities, permissions, observations, artifacts, checkpoints — **no secrets**. Checkpoints before state-changing work; for WRITEs: intent + approval + inputs + expected result.

Deliverable contract before deep investigation (diagnosis, evidence, causes, uncertainties, actions). Stop conditions: success, failure, iteration/time/tool budgets, escalation.

Verification before COMPLETE: sections, evidence, tool success, blockers, write verification.

Skills = versioned procedures (owner, last verified, tests) loaded JIT from Packs/knowledge — **not** a runtime.

---

## Write governance (voice and text)

READs: automatic if authorized and compiled. WRITEs: risk-based. Financial / external / destructive / HR / security: explicit. Add **financial class labeling** on ActionSpec without auto-exec.

Ambiguous audio must not commit WRITE. Spoken approval bound to PendingAction.

Prompt-injection: CRM notes, tickets, docs, web are **data**.

---

## Response semantics

One Composer object; render:

`TEXT_DETAILED` | `TEXT_COMPACT` | `VOICE` | `PROGRESS` | `APPROVAL` | `ERROR` | `ARTIFACT_SUMMARY`.

Default: **answer first, evidence second, detail on demand.** Voice: headline, critical fact, next step. No markdown in TTS. No raw chain-of-thought in storage or UI.

---

## Memory / outcomes / proactive

**REUSE** HMAC memory. **DEFER** closed-loop business-impact learning until READ observations are trustworthy (2.0-K). **DEFER** proactive attention (2.0-M / 3.0-J) until reactive is live-proven. Attention ranking: impact, urgency, confidence, relevance, actionability, novelty — no invented SKUs.

---

## Evaluation and observability

Keep goldens A–G. Add: department, voice interrupt/correction, text↔voice ID continuity, long-task, adversarial (ambiguous names, stale metadata, injection, mid-WRITE interrupt).

Shadow: old vs 3.0 **READ/plan only**; no duplicate external writes. Canary: internal org → test org → small cohort → capability → connector family. Flags + rollback.

Every task reconstructable: objective, semantics, context loaded, tools exposed, plan, actions, provenance, approvals, provider calls, observations, repairs, result, outcome. Cost tracked after correctness.

---

## Migration and rollback

- Feature flags per 3.0 phase.
- HMAC remains on existing F1 keys.
- SC fast path remains until generic compile matches quality, then **same gate**.
- Voice lane B/C never default until benchmark + Cesar approval.
- Rollback = previous flag set; never remove `enforce_invoke_preflight` on sealed keys.

---

## Production proof

PASS requires: `/health` `git_sha`, `audit_events` timestamp+action, conversation/run id, or CI URL that exercised the **live** path. Dual `/ai` and `/agents/[id]/chat` until one gate. Local pytest ≠ production-fixed.

---

## Required diagrams

### A. Complete 3.0 runtime

```
User ──text/voice/agent/workflow──► Ingress
                                      │
                    ┌─────────────────┴─────────────────┐
                    │         Intelligence Core          │
                    │  E1 → E5 shell → E4 → strategy     │
                    │  F1 preflight → invoke → Observe   │
                    │  Composer → E2                     │
                    └─────────────────┬─────────────────┘
           interaction render          work persistence
           (ack/progress/voice)        (plan, artifacts)
```

### B. Interaction loop vs work loop

```
speech/text in → INTERACTION (ack, barge-in, corrections)
                      │ same plan_id
                      ▼
                 WORK (compile, tools, repair, verify)
                      │
                      ▼
                 Composer renders channel
```

### C. Cascaded voice (lane A)

```
mic → AEC/NS → VAD/turn → Deepgram partial/final
    → kernel spoken_mode → Composer progress/final
    → ElevenLabs stream → speaker
Interrupt: stop TTS context; kernel interrupt; no WRITE if uncommitted
```

### D. Native realtime candidate (lane B)

```
mic → realtime speech model (eval)
    → tool/work requests **only** via canonical execute_task_streaming
    → audio out
Forbidden: model-native tools that skip HMAC/approval
```

### E. Hybrid realtime (lane C)

```
realtime conversation frontend (turn, barge-in, TTS)
    → Gravitre work backend (E1–E5/F1)
    → progress + final facts back to frontend
```

### F. Fast READ

```
E1+time+resource → E4 → NO_MODEL/FAST → F1 HMAC → invoke → Composer
```

### G. Deep investigation

```
Deliverable contract → hypotheses on E5
→ join plan → parallel safe READs → evidence update
→ verify / insufficient-evidence honesty → Composer
```

### H. Long-running work

```
CREATED→…→WORKING (background OK)
checkpoint → WAITING_* → resume same plan_id
artifacts + verify → COMPLETED|PARTIAL|FAILED
```

### I. WRITE approval

```
compile facts → risk class → PendingAction
spoken/text confirm exact target → execute → verify
"yes—wait" before commit → cancel
```

### J. Repair loop

```
fail → classify → recoverable?
  yes → cheapest safe repair (budget) → retry/replan
  no  → WAITING_USER / FAILED
error memory in-task
```

### K. JIT context

```
ids + summaries → score → include/exclude trace
miss → retrieve → cache by revision
```

### L. JIT tool discovery

```
capability + sources + availability
→ eligible ActionSpec set (search if needed)
→ model sees N tools, not 732
```

### M. Entity join

```
BusinessEntity (org)
  bindings[system, type, id] + evidence + confidence
  never silent merge below threshold
  Memory HMAC exact; fuzzy names out of scope without owner
```

### N. Checkpoint / resume

```
before WRITE: save intent, approval id, inputs, expected
crash/interrupt → load checkpoint → continue or replan
no secrets persisted
```

### O. Text↔voice continuity

```
voice media session (ephemeral)
        │
        ▼
durable task/plan (persistent)
        │
        ▼
later text client loads same plan_id / entities / PendingAction
```

---

## Research decision table

| Source (public behavior) | Behavior | Solves | Applicable? | Existing equivalent | Adaptation | Risk | Benchmark |
|--------------------------|----------|--------|-------------|---------------------|------------|------|-----------|
| Manus-like operators | Long autonomous work, artifacts, resume | Endless chat, lost state | Yes, **after** compile cohesion | E5 + workflows | Durable session + checkpoints on E5 | Second runtime | Long-task golden; no extra WRITE |
| Claude Cowork-like | Delegated knowledge work, human takeover, files | Clarification storms | Yes | Packs, knowledge, pending | Skills as JIT procedures | Skill-as-agent | Human takeover same plan_id |
| ChatGPT-like realtime | Native audio, barge-in, backchannel | Stiff cascade UX | Eval only | Cascade + Metric A/B | Lane B/C eval; keep kernel for tools | Ungoverned tools | A vs B vs C table |
| Full-Duplex-Bench / EVA-Bench | Separate first-audio vs tool completion | Blended “latency” lies | Yes | Two-metric SLO | Keep A/B; extend traces | Gaming Metric A with fake ack | Existing voice-slo-gates |
| Gemini Live / GPT-Realtime published numbers | Tool turns seconds not sub-500ms complete | Unrealistic SLOs | Yes | Metric B 5s/8s | Do not “beat” with skipped compile | Skipping F1 | Shadow only |
| Classic RAG “stuff the window” | Dump all memory/tools | — | **No** | E4 | JIT opposite | Token/latency | Context efficiency evals |

Do not cargo-cult: no vendor tool-calling bypass, no fuzzy memory, no Certified chrome, no speculative WRITE.

---

## Phase plan (reordered from 2.0 audit, not the 3.0 prompt’s default)

Live proof and measurement **before** new autonomy.

| Phase | Objective | Why this order | Depends | Protected | Gate |
|-------|-----------|----------------|---------|-----------|------|
| **3.0-A** Gap closure + baseline | Finish 2.0-A cohesion live-proof; HMAC companions if still open; Composer-only prose; plan lineage; **instrument full latency trace**; publish A/B baselines | Re-audit P0; unknown critical path | Flags, isolated org | WRITE/HMAC/G8 | LIVE_USER_PROVEN traffic + trace artifact + SHA |
| **3.0-B** Context/tool efficiency | JIT context scoring + eligible-tool namespace; no 700-tool dump; cache ActionSpecs | Token/serial compile suspects | A baseline | F1 eligible set | Token + stage p50/p95 not worse |
| **3.0-C** Realtime voice 3.0 | Semantic endpoint, backchannel, barge-in WRITE safety, ASR lexicon; **eval** lanes A/B/C | Voice UNKNOWN | A+B | No speculative WRITE | Metric A not worse; interrupt traces |
| **3.0-D** Durable work sessions | E5 state machine, background, checkpoint, artifacts, deliverable contract | Cowork value | A | Same plan_id | Resume golden |
| **3.0-E** JIT tools + skills | Tool search, examples, versioned procedures | 732 catalog | B, D | Not a new runtime | Eligible-set tests |
| **3.0-F** Reasoning / parallel READ | Hypothesis steps, join **when entity store exists**, parallel safe READs | CS-12 | C recipes / entity | Honesty if insufficient evidence | “why pipeline” golden |
| **3.0-G** Repair / checkpoint / resume | Classed F2 + error memory | Post-provider WEAK | D, F | Bounded budgets | Repair traces |
| **3.0-H** Cross-system entities | BusinessEntity bindings | CS-13; STA-312 owner | Named owner | No silent merge | Join tests + live |
| **3.0-I** Governed voice WRITE | Spoken approval, yes-wait, stable targets | Voice WRITE UNKNOWN | C | Approval UX | Spoken confirm traces |
| **3.0-J** Proactive attention | Ranked safe READ notices | 2.0-M | F, G | No auto high-risk WRITE | Quiet tests |

**Do not start 3.0-C lane B production or 3.0-D as a new worker product before 3.0-A gate.**

---

## First implementation recommendation

**Single highest-leverage first phase: 3.0-A — 2.0 gap closure + latency/critical-path baseline.**

Prefer measurement and convergence over new autonomy while the runtime is a **TEST_PROVEN compiler island** and **not LIVE_USER_PROVEN**, and while voice stages are uninstrumented. Adding Cowork sessions or native-realtime models first would hide STT vs TTFT vs provider vs TTS and risk a second execution core.

---

## Completion criteria (program)

3.0 is **not** “replace Deepgram+ElevenLabs” or “HMAC all 732.” It is:

1. Same Intelligence Core; interaction/work loops share IDs.  
2. Operational compile+preflight before strategy (SC = fast path).  
3. JIT context/tools; no 700-tool prompts.  
4. Voice Metric A/B held; barge-in safe near WRITE.  
5. Durable E5 sessions with artifacts and resume.  
6. WRITEs compiled **and** approved; spoken approval explicit.  
7. Goldens A–G plus 3.0 suite; shadow without duplicate WRITEs.  
8. No customer certification chrome; no invented prices/Enable.

---

## STOP

GRAVITRE PLATFORM EXECUTION 3.0 SPEC READY: **YES** (spec/plan only; named 2.0 “final audit” + JSON ledger files were **missing** — ingested re-audit + 2.0 spec instead)

2.0 BLOCKERS THAT MUST CLOSE FIRST:

1. LIVE_USER_PROVEN F1/SC traffic (`conversation_id` + `audit_events` + `/health` SHA) and isolated golden smoke artifact  
2. Invariant I: compile-before-strategy; HMAC SC companions; Composer-only prose  
3. WRITE/`react_write_gate`/HMAC/G8 must not be weakened; CI standing-red named or fixed  
4. Voice Metric A/B + barge-in-near-WRITE still unproven on current tip  
5. Entity joins blocked on named PII owner (STA-312); `compiled_task` must stay OPTIONAL_PROJECTION  

TOP 3.0 ARCHITECTURAL PRIORITY: **One core, two loops (interaction vs work), compile+HMAC before strategy, JIT context/tools, measured voice cascade before any native-realtime swap.**

FIRST IMPLEMENTATION PHASE: **3.0-A Gap closure + full latency trace baseline** (after Cesar approval). Do not start automatically.

EXPECTED USER-VISIBLE IMPROVEMENT: Honest fast ack on real work; fewer fork-dependent “ask for property_id / last 30 days / Stopped.” failures on the F1/SC island; progress that does not claim success early.

EXPECTED LATENCY IMPROVEMENT: **None claimed until 3.0-A publishes before/after p50/p95 by stage.** Standing voice targets remain Metric A P50&lt;500ms / P95&lt;800ms and Metric B P50&lt;5s / P95&lt;8s — 3.0-A **measures** whether current tip meets them.

MAIN REGRESSION RISK: A second cognitive core (realtime model tools or Cowork worker) skipping F1/approval; speculative WRITE from partial ASR; Metric A gamed with empty acks; fuzzy memory; invented product chrome.

**Stop for Cesar review. Do not implement 3.0 until this architecture is approved.**

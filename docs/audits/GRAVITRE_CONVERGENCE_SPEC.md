# GRAVITRE CONVERGENCE SPECIFICATION

**Status:** AUTHORITATIVE — **H0 APPROVED 2026-09-22** with binding amendments (H13 removed as Cesar stop; physical-mic HUMAN_EXPERIENCE_PENDING retained; engineering-complete ≠ all-IDs-processed; deferred Section 0 gaps preserved). Continuous execution authorized for P0–P6 + M. Do **not** build Computer Use or a 3.0 rewrite.  
**Direction:** PRESERVE + CONVERGE  
**This is one program.** The product experience contract **is** Section 0 of this file. The phases below **are** the technical work required to achieve it. There is no second plan.

**Active documents (one program, not competing plans):**

1. **This specification** — product contract (Section 0) + technical work + binding IDs  
2. **Backlog:** `GRAVITRE_CONVERGENCE_BACKLOG.md`  
3. **Execution ledger:** `docs/delivery/GRAVITRE_CONVERGENCE_EXECUTION_LEDGER.md` + `gravitre-convergence-execution-ledger.json`  
4. **Gaps register:** `docs/delivery/GRAVITRE_CONVERGENCE_GAPS_AND_EXCEPTIONS.md`

H0 (2026-09-22) authorizes **continuous execution** of the entire approved scope. Do not stop for per-phase approval. Independent acceptance audit remains a later separate stage.

Evidence (historical): `GRAVITRE_EVIDENCE_CLOSURE_2026.md`  
Baseline backend: Railway `a7a0dd56` · isolated org `f07e57c0-1501-4000-8000-c04e57a00001` · never operator org `cbbf993b-…`

---

# SECTION 0 — PRODUCT EXPERIENCE AND EXECUTION CONTRACT

This section governs **every** engineering decision in this specification and backlog.

ChatGPT, Claude, Manus, Claude Cowork/artifacts, and Grok-style computer agents are **behavioral references**, not architectures to replicate. Extract useful behaviors and implement them through Gravitre’s existing intelligence, task, memory, execution, governance, and Composer.

Do not create separate products for conversational AI, voice, workflows, agents, design, or browser execution. The user experiences **one Gravitre**.

## Non-negotiable product standard

**Conversational intelligence.** Natural text and voice with the fluency, contextual understanding, reasoning quality, responsiveness, and communication standards users expect from leading assistants.

**Autonomous productivity.** Business-task execution with multi-step autonomy, governed read/write, visible progress, artifact creation, human collaboration, and verified results.

## 0.1 Natural-language intake

The user must not need Gravitre internals. They express a business objective in ordinary language (“How is my business doing?”, “Find out why our leads dropped.”, “Take care of the follow-up, but let me approve anything that gets sent.”).

Gravitre determines intent, objective, business context, entities, required evidence, capabilities, execution strategy, permissions, and approvals.

Do not ask for connector names, API actions, property IDs, schema fields, or parameters Gravitre can safely discover. Clarify only when a material ambiguity remains.

## 0.2 Text response standard

Text should feel like a capable assistant, not a developer trace. Natural professional tone; direct answers; appropriate depth; strong reasoning; context retention; useful follow-ups; concise vs structured by task; honest uncertainty; no invented provider results; no unnecessary clarification; no leaked connector vocabulary; no excessive status narration; clear planned / executing / completed / verified / failed / blocked.

Do not impose one response shape on greeting, analysis, campaign creation, workflow, and financial report.

## 0.3 Natural voice-to-voice standard

Voice is a first-class interface to the **complete** platform. Support natural speech, hesitation, self-correction, interruption, backchannels, follow-ups, pronouns, references, business vocabulary, spoken clarification, cancellation, approval, progressive speech.

Voice is not a restricted text mode. Equivalent text and voice requests share intent, entities, time, capability, resource, plan, execution, approval, and outcome. Spoken render may be shorter; truth is identical. Target: natural dialogue, not command-and-response software.

## 0.4 Autonomous execution standard

Complete business objectives; do not only explain how. Loop: UNDERSTAND → PLAN → EXECUTE → OBSERVE → ADAPT → VERIFY → DELIVER → LEARN.

Strategy may be API connector, workflow, agent delegation, background job, or (later) browser/computer. The strategy is **not** a new intelligence system. Same canonical task truth, governance, provenance, Observations, and completion semantics.

## 0.5 Read/write productivity standard

READ: discover, search, retrieve, compare, analyze, investigate, verify.  
WRITE: draft, create, update, organize, prepare, submit, publish, send.

Consequential external actions stay governed. A compiled plan is not a completed task. A successful API response is not a successful business outcome. The final response must report what was actually accomplished.

## 0.6 Finished output and artifact standard

Deliver useful finished work (plans, assets, reports, analyses, documents, CRM updates, drafts, recommendations, verified actions). Artifacts remain bound to task, evidence, execution history, and approval. A paragraph describing a deliverable is not the deliverable.

**This program does not build** a design/asset studio or campaign factory. It must not make later artifact work require a second brain (P7 freeze).

## 0.7 Visible execution and human collaboration

The user should understand what Gravitre is doing without developer logs. Meaningful progress during long-running work. Browser/computer (when implemented later) is a visible session, not a text simulation. Watch, inspect, pause, take over, correct, approve, resume — same task and governance. No browser-agent brain.

## 0.8 Seamless cross-modal continuity

One business task survives text, voice, desktop, mobile, AI workspace, workflow, agent, and computer. Example: voice while driving → desktop shows the same task, evidence, artifacts, progress, approvals → mobile approve → outcome recorded. The user does not start over.

## 0.9 Speed and responsiveness standard

Measure separately: time to acknowledgement, first useful text, first useful speech, first execution progress, first business result, completed work, verified outcome.

Fast acknowledgements must not disguise slow work. Do not buy latency by weakening reasoning, accuracy, governance, or quality. Use measured evidence for routing, context, cache, tools, parallelism, streaming, voice, and Composer.

## 0.10 Business intelligence and learning standard

Use existing KF, entities, memory, and outcome systems. Loop: business evidence → understanding → decision → action → observation → measured outcome → learning → improved later decision.

Learning is evidence-based, tenant-safe, and correctable. Storing a conversation, tool result, or outcome row is **not** “Gravitre learned.”

## 0.11 End-to-end acceptance

Do not certify the product by testing only parts. Score whole journeys on: (1) NLU (2) reasoning and evidence (3) model and strategy (4) governed execution (5) progress (6) verification (7) natural explanation (8) finished output where requested (9) follow-up continuity (10) text/voice equivalence (11) latency and effort (12) task and business outcome recording.

Classify: **ANSWERED · PLANNED · EXECUTING · PARTIALLY_COMPLETED · COMPLETED · VERIFIED · BLOCKED · FAILED**.  
`tool.invoke.completed` ≠ completed user work.

## 0.12 Engineering decision rule

Every phase must answer: **What specific user-visible improvement does this deliver toward Section 0?**

If a change only moves an internal metric, justify it as reliability/maintainability or drop it. If it creates a parallel system, duplicated task state, a separate intelligence layer, or inconsistent modality behavior, reject the design.

Default: preserve and improve healthy components. Do not rebuild Gravitre. Do not clone competitors.

## 0.13 Final product acceptance question

Can a user naturally express a business objective through text or voice, have Gravitre intelligently understand and execute the work across appropriate systems, observe progress, receive an accurate and useful finished result, continue the same task across devices, and benefit from the business intelligence gained over time?

**Today: no.** Gaps and the phases that close them are §3.

---

# SECTION 1 — TECHNICAL CONTRACT

## 1.1 One intelligence, many strategies

Ingress: `execute_task_streaming` (text and `spoken_mode`).

**Shared for every strategy:**

1. ExecutionPlan (plan_id, capability, steps, terminal state)  
2. ActionSpec (action_key, HMAC, parameter provenance)  
3. Governance (`write_allowed`, PendingAction, tenant isolation, execution identity)  
4. Observation (success, provider_invoked, result identity, empty, error class; no secrets)  
5. Terminal state (completed / pending_approval / blocked_auth / failed / clarified)  
6. Composer (sole user-facing prose: shortcut / canned / success / clarify / spoken)

**Strategies (not products):**

| Strategy | When | Model loop |
|----------|------|------------|
| Sealed compiled READ | HMAC READ compiled (e.g. HubSpot `deals.list`) | **None required.** LIVE must not re-select tools. |
| Unified LIVE | Ambiguous, missing slots, conversational, LIVE-executable tools | LIVE may finish without ReAct |
| ReAct | Legitimate fallback: pending-family, `defer_classical_tool_sse`, bounded repair — **not** a second tool-choice after LIVE already proposed the same class | Bounded |
| Workflow child | Temporal/asyncio | Same ActionSpec + Observation; no HMAC/Composer bypass |
| Browser/computer | **Not built this program** | Same plan + PendingAction + Observation |

**Invariant:** LIVE does **not** own every tool turn. Sealed compiled READ is canonical for compiled HMAC reads.

**Release identity:** compatible **release pair** (Railway `/health` SHA + Vercel production SHA + git ancestor check). Identical frontend/backend/git SHAs are **not** required. Accidental divergence = frontend SHA is not a descendant of backend SHA.

## 1.2 Where existing fabrics enter

Preserve Knowledge Fabric, entity fabric, outcome events, and ML infrastructure. They enter only here:

| Fabric | Plan | Execute | Learn later |
|--------|------|---------|-------------|
| Knowledge Fabric (pgvector) | After the **capability evidence plan** lists required providers | Never replaces a required live READ | Chunk provenance |
| Entity fabric (HMAC) | Exact who/what; STA-312 no fuzzy person join | Bind ActionSpec params | Mentions, not guesses |
| durable_checkpoint | Working memory for the objective | Resume without full history replay | Not a KPI |
| Outcome events | `outcome_bias_section` only for BUSINESS_IMPACT / labeled events | API 200 is not business success | Persist impact when a human/KPI exists |
| JIT MiniLM | Narrow **eligible** tools after the capability gate | Not business truth | Unchanged |
| Trained ML weights | None serving the kernel today | Do not invent serving | Do not train until labels exist |
| Intelligence UI | Display | Never execute | Never a second OS |

## 1.3 Disposition

Default **PRESERVE**.

| ID | Subsystem | Disposition | Do not |
|----|-----------|-------------|--------|
| D1 | `execute_task_streaming` | PRESERVE | Second runtime |
| D2 | CognitiveTurnKernel | PRESERVE | Replace |
| D3 | Sealed compiled READ / HMAC | PRESERVE | Force through LIVE |
| D4 | Unified LIVE | CONVERGE (no dual select) | Own sealed READ |
| D5 | ReAct | PRESERVE (repair/fallback) | Delete before P1 |
| D6 | Fallthrough enum | CONVERGE as router | Treat volume as automatic defect |
| D7 | ActionSpec / PendingAction | PRESERVE | Bypass |
| D8 | Composer shortcut/canned | PRESERVE | “Fix 19.9s” via Composer |
| D9 | Pipecat / Deepgram / ElevenLabs | PRESERVE | Replace cascade this program |
| D10 | PCM interrupt | OPTIMIZE origin/turn-state | Global suppress until STT final |
| D11 | Knowledge Fabric | PRESERVE supplemental | Replace provider READ |
| D12 | Entity fabric | PRESERVE | Fuzzy person join |
| D13 | Outcome events | PRESERVE; gated consume | Train on API 200 |
| D14 | Workflow / Temporal | CONVERGE Observation + task id | New engine |
| D15 | durable_checkpoint | PRESERVE | New memory product |
| D16 | Release pair | PRESERVE | Identical SHA rule |
| D17 | Prod model tier low | HOLD until M signed | Silent upgrade |
| D18 | Computer / Playwright interact | EXTEND later | Build this program |
| D19 | Second cognitive runtime | NEVER ADD | — |

---

# SECTION 2 — PHASES

Each phase has one objective, architecture contract, scope, baseline, acceptance, rollback, and a Section 0 user-visible improvement.  
**P0 is standing. M runs in parallel from day one.**  
Do not optimize P2 until investigation marks exist. Do not build computer use.

### P0 — Standing invariants

**Section 0:** 0.5, 0.11 — governed READ remains completed work.  
**Objective:** Every change keeps sealed compiled READ, the six shared contracts, and a documented release pair.  
**Reuses:** HMAC HubSpot path, Composer canned, release-pair file.  
**Scope:** Regression + release-pair process. No rewrite.  
**Baseline:** conv `0d35dba2-…` @ `a7a0dd56`, `hubspot.deals.list`, 25 deals, canned, 19931 ms first text.  
**Acceptance:** After any merge, isolated `Show my deals.` still that contract; release pair updated.  
**Rollback:** Revert merge; prior Railway image.  
**User-visible:** CRM count answers keep working.

### P1 — Single selection for exploratory turns

**Section 0:** 0.1, 0.4, 0.9 — one mind, less delay, still executes.  
**Objective:** Exploratory requests must not pay LIVE tool-selection and then ReAct tool-selection for the same need.  
**Contract:** If sealed/compiled READ will own the turn, skip LIVE. If LIVE cannot execute its connector proposal, one-shot handoff **without** a second model tool-choice. Preserve `pending_family_classical_resume`, `defer_classical_tool_sse`, bounded repair.  
**Reuses:** fallthrough enum, `sealed_read_execution`.  
**Scope:** routing only. No HubSpot adapter patches.  
**Baseline:** conv `2859eecc-…` LIVE `gpt-5.4-mini` 1390 ms + schema retry 1742 ms then `read_tool_classical` + ReAct; first text 31140 ms. 24h isolated: defer 38 / pending-family 19 / read_tool_classical 14.  
**Acceptance:** Repeat CEO prompt: zero turns with both LIVE tool-selection and `agent.react.iteration` tool-selection. Pending-family and defer-SSE still occur when those reasons apply. HubSpot sealed READ still skips LIVE.  
**Rollback:** Flag default-off.  
**User-visible:** Exploratory asks do not feel like two planners.

### P2 — HubSpot first-text critical path

**Section 0:** 0.2, 0.9 — first useful business text sooner; do not thin reasoning or HMAC.  
**Objective:** Measure which stages consume ~19.9 s before first useful text on sealed HubSpot READ. Composer is already canned.  
**Contract:** Stage marks: understanding, memory.recalled, preflight, provider, compose_canned, first_sse. Investigation has no behavior change. Optimize only after marks, only safe parallelism. No vendor HubSpot patch.  
**Reuses:** `turn_latency_trace`.  
**Baseline:** 19931 ms first text / 23199 complete / canned / latency_audit `{spoken_mode:false}` only.  
**Acceptance (investigate):** Waterfall JSON on current `/health` SHA, stages sum to wall ±10%. **Optimize:** after marks, implement the **safest evidence-backed** optimization within this P2 architecture, acceptance criteria, and rollback. Stop only if the correction would materially change architecture, scope, governance, paid infrastructure, or safety. HubSpot 25-deal PASS. Name the p50 target from the waterfall. No Composer rewrite; no HubSpot-only vendor hack.  
**Rollback:** Remove marks / optimize flag.  
**User-visible:** After optimize only — first CRM sentence arrives sooner.

### P3 — PCM interrupt as origin and turn-state

**Section 0:** 0.3 — voice is the full platform and must speak; real barge-in stays.  
**Objective:** Synthesized/chunked inbound PCM must not cancel the assistant as user barge-in, **without** globally ignoring real human barge-in until STT final.  
**Contract:** Origin `user_mic` | `probe_pcm` | `tts_echo`. State `listening` | `committing_utterance` | `speaking`. Suppress interrupt only for non-`user_mic` or overlapping send/commit. `user_mic` during `speaking` remains live. Keep Pipecat/Deepgram/ElevenLabs. HTTP Talk unchanged.  
**Baseline:** PCM empty `assistant_text`, interrupts before transcript, 0 audio frames. HTTP Talk greeting first audio 224 ms.  
**Acceptance:** Same SAPI phrase spoken (or connector-status shortcut); interrupt_events during send = 0. Unit: `user_mic` still stops TTS. Physical mic remains authorization-gated.  
**Rollback:** Origin policy flag off.  
**User-visible:** Voice answers; interrupting with a real mic still works.

### P4 — Business-capability evidence plan

**Section 0:** 0.1, 0.4, 0.5, 0.10 — natural ops questions use current provider evidence.  
**Objective:** CEO/ops questions build a required evidence list (connected providers first) before JIT/KF ranking. KF may add context; it must not replace a required live Observation. Missing auth → blocked/pending_auth prose, not workflow plumbing.  
**Reuses:** capability recipes, sealed READ, ContextCompiler, KF, entities.  
**Baseline:** CEO prompt used KB, workflow runs, agent status, connector status; skipped healthy HubSpot and Google Ads; GA pending_auth.  
**Acceptance:** ≥1 HubSpot or Ads Observation **or** explicit GA/GSC pending_auth; must not answer only from workflow/agent/KB. Sealed “show deals” unchanged.  
**Rollback:** Recipe gate flag.  
**User-visible:** “How is my business?” talks about the business or honest gaps.

### P5 — Workflow child = same task

**Section 0:** 0.7, 0.8 — one task, inspectable progress.  
**Objective:** Workflow steps share task identity and emit canonical Observations; Composer narrates when a human is waiting.  
**Contract:** `tool_context_from_step` is not an HMAC/Composer bypass. Child Observations carry `plan_id` / `conversation_id` / `durable_checkpoint` when attached to a user task.  
**Baseline:** CODE `cognitive_invoke=False`. Live child loop UNKNOWN — first slice is a live trace.  
**Acceptance:** One isolated child Observation sharing parent `plan_id` (or documented detached job id); Composer can narrate it; WRITE still HMAC.  
**Rollback:** Adapter flag.  
**User-visible:** Chat-started work continued by a workflow is the same job.

### P6 — Outcome learning consume (gated)

**Section 0:** 0.5, 0.10 — HTTP 200 is not a business win.  
**Objective:** Later plans change only from tenant-isolated BUSINESS_IMPACT / labeled events.  
**Reuses:** `intelligence_outcome_events`, `outcome_bias_section`. No new ML platform.  
**Baseline:** 7d sample n=50, `business_metric_improved` = 0.  
**Acceptance:** After a human-authorized labeled impact event, the next related plan includes `outcome_bias_section`. No invented KPIs.  
**Rollback:** Stop injecting bias.  
**User-visible:** Later advice can cite real prior outcomes only when they exist.

### P7 — Computer strategy freeze (no build)

**Section 0:** 0.6, 0.7 — later visible work stays one Gravitre.  
**Objective:** Browser/computer remains a future **strategy** on §1.1.  
**Reuses:** ExecutionPlan, PendingAction, Observations, durable_checkpoint, Composer, AI Workspace; eval note in `GRAVITRE_COMPUTER_EXECUTION_EVAL.md` (design evidence, not a second plan).  
**Acceptance:** No browser-agent brain merged.  
**User-visible:** None this program.

### M — Model-tier benchmark (parallel from day one)

**Section 0:** 0.2, 0.9, 0.12 — routing only with signed evidence.  
**Objective:** Compare `low` vs `medium_high` (and failover families) on identical compiled tasks. Do not assume low is enough or medium_high is better.  
**Tasks:** simple conversation, complex business reasoning, tool selection, ambiguous entity, multi-source synthesis, safe WRITE compile, evidence verification, voice-length render. **n ≥ 5** per cell. Metrics: checklist pass, tool_key correctness, latency, tokens, cache, cost, fallbacks.  
**Decision:** Keep `low` unless medium_high improves tool_selection + verification + WRITE compile enough to justify latency/cost — Cesar signs. Route up only for named shapes. Sealed READ stays modelless.  
**Baseline:** prod LIVE tier `low` / `gpt-5.4-mini`. Direct bake-off UNKNOWN (no local key).  
**Acceptance:** Scorecard filled; **prod default unchanged** until Cesar signs.  
**Rollback:** Keep tier=low.  
**User-visible:** None until a signed routing change.

---

# SECTION 3 — GAPS VS THE FINAL ACCEPTANCE QUESTION

| Missing behavior | Existing component | Phase | Evidence | Acceptance |
|------------------|--------------------|-------|----------|------------|
| CEO NL skips live CRM/ads | Recipes, sealed READ, JIT | P4 | T-ceo used KB/workflows | Business Observation or pending_auth |
| Dual LIVE+ReAct selection | Fallthrough | P1 | `2859eecc-…` | No dual tool-choice |
| ~20s to first deal sentence | Sealed READ (Composer canned) | P2 | 19931 ms | Waterfall then evidence-backed opt |
| PCM silent after STT | Pipecat interrupt | P3 | empty assistant_text | Spoken; user_mic barge-in kept |
| Workflow not proven same task | `tool_context_from_step` | P5 | cognitive_invoke=False | Child Observation + plan_id |
| Cross-device resume unproven | conversation_id, checkpoint | P5 + §4 journeys | earlier checkpoint LIVE | Same id text→voice→approve |
| Learning not proven | outcome events | P6 | 0 impact / 50 | Bias only after labeled impact |
| Artifacts / visible computer | SSE, httpx READ | P7 freeze | Playwright off | No second brain |
| Default quality vs leading assistants | MODEL_TIERS | M | LIVE low | No silent tier change |

**This program’s target** is to close P1–P6 + P3 voice speak + P0 non-regression on connected isolated-org systems. It does **not** claim the full Section 0 product (campaign assets, computer live-view, human-mic LIVE_PROVEN) is done.

---

# SECTION 4 — EVALUATION CONTRACT

Org: `f07e57c0-…` only. Record Railway SHA + Vercel SHA every run. Compare only same backend SHA or label NOT COMPARABLE.

## 4.1 Baselines (`a7a0dd56`)

| ID | Path | First useful | Complete | Class today |
|----|------|--------------|----------|-------------|
| T-greet-warm | Hello again | 2092 ms | 5081 ms | ANSWERED shortcut |
| T-hs-read | Show my deals. | 19931 | 23199 | COMPLETED count-only (not VERIFIED line items) |
| T-hs-follow | Only the large ones. | 16787 | 19495 | ANSWERED (must not invent cutoff) |
| T-write | Send Sarah a summary. | 15756 | 18750 | ANSWERED clarify |
| T-ceo | How is the business… | 31140 | 33703 | PARTIALLY_COMPLETED |
| V-http-hi | HTTP Talk Hi | text 220 / audio 224 | 1204 | COMPLETED audio (not physical mic) |
| V-pcm-apollo | SAPI Apollo | STT OK | empty speech | FAILED spoken delivery |

## 4.2 Phase gates

| Phase | Pass | Fail |
|-------|------|------|
| P0 | T-hs-read canned 25 + HMAC | Ungoverned WRITE |
| P1 | No LIVE+ReAct dual tool-choice; T-hs-read sealed | Dual select; pending-family broken |
| P2 inv | Waterfall JSON | Optimizing without marks |
| P2 opt | TTFT vs **this** waterfall; T-hs-read PASS; no material architecture change | Composer rewrite; HubSpot-only hack |
| P3 | V-pcm spoken; user_mic unit true | Global suppress-until-STT-final |
| P4 | T-ceo business Observation or explicit pending_auth | KF/workflow-only CEO answer |
| P5 | Child Observation shares plan/task id | HMAC bypass |
| P6 | Bias only after labeled impact | API 200 as business win |
| M | Scorecard; no prod change | Silent default tier change |

## 4.3 Journey scorecard

Score §0.11’s twelve items on: greeting; deals + follow-up; Sarah WRITE; CEO; PCM Apollo; HTTP Talk hi; chat→workflow child; text then spoken same conversation.  
Campaign artifacts and visible computer are **out of this program’s completion target**.

---

# SECTION 5 — HUMAN / PROVIDER AUTHORIZATION

| # | Action | Unblocks | If skipped |
|---|--------|----------|------------|
| H0 | Cesar approves **this** specification | All code | No implementation |
| H1 | Keep HubSpot healthy on isolated org | P0 | READ BLOCKED |
| H2 | GA OAuth | P4 traffic | BLOCKED honest |
| H3 | GSC reconnect | P4 remaining-source | BLOCKED |
| H4 | Gmail OAuth if email WRITE in scope | later | pending_auth |
| H5 | QBO if finance in scope | later | leave pending |
| H6 | Confirm Google Ads stays healthy | P4 Ads | HubSpot-only CEO |
| H7 | Eval API keys | M | Routing UNKNOWN; prod stays low |
| H8 | Sign M scorecard before prod tier change | M.3 | Keep low |
| H9 | Physical-mic LIVE_PROVEN (driving/hands-free) | Final **product** acceptance; **HUMAN_EXPERIENCE_PENDING** while engineering continues | Must remain in gap register + independent audit; not optional disappearance |
| H10 | Do not enable prod WebRTC | — | keep deny |
| H11 | Optional labeled business impact event | P6 live consume | P6 wiring-only; IMPLEMENTED_PROOF_PENDING |
| H12 | Browser SSO only if UI gates added later | — | not required for P1–P5 kernel |
| H13 | **Removed as Cesar stop (H0 amendment).** After P2 marks, Cursor implements safest evidence-backed optimization in-scope. | B2.3 | Stop only for material architecture/scope/governance/paid-infra/safety change |

**Never authorized:** governance bypass, operator-org kernel chat, invented prices/Certified/Enable, Computer Use build, Lane B production audio.

---

# SECTION 6 — OUT OF SCOPE

Gravitre 3.0 rewrite; new planner/memory/voice/intelligence brain; LIVE owning sealed READ; global barge-in hold until STT final; default model upgrade without signed M; computer/browser implementation; invented customer surfaces; operator-org tests; separate conversational/voice/agent/browser products; certifying the product by unit tests of parts only; competing documents treated as active plans.

---

# APPENDIX — SUPERSEDED DECISIONS

Not active requirements:

1. Identical git / Railway / Vercel SHAs  
2. LIVE must own every tool turn  
3. Composer is the HubSpot 19.9s tax  
4. Globally ignore barge-in until STT final  
5. Ban Knowledge Fabric  
6. Default medium_high because low is outdated  
7. Optimize compiled READ before instrumentation  
8. Computer Use in this program  
9. Delete ReAct immediately  
10. Multiple concurrent “plans” (product contract vs baseline vs old phase 0–9)

Historical write-ups under `docs/audits/` remain evidence. They are **not** alternate specifications.

---

# SECTION 7 — BINDING REQUIREMENT CATALOG

Every item has a stable ID. Status lives only in the execution ledger. IDs must not be deleted. Terminal states: `IMPLEMENTED_AND_VERIFIED` · `IMPLEMENTED_PROOF_PENDING` · `EXTERNALLY_BLOCKED` · `FAILED` · `NOT_IMPLEMENTED` · `APPROVED_SCOPE_EXCEPTION`. Standing preserves remain in the ledger until program close as regression requirements.

Full rows: `docs/delivery/gravitre-convergence-execution-ledger.json`.

### 7.1 Product experience (Section 0)

| ID | Dim | Requirement | Phase |
|----|-----|-------------|-------|
| REQ-PX-001 | cohesion | One Gravitre; no separate conversational/voice/workflow/agent/browser products | P0 |
| REQ-PX-002 | converse | Text meets ChatGPT/Claude-class fluency/reasoning/honesty (behavioral, not clone) | P0,M |
| REQ-PX-003 | voice | Voice is first-class to the same platform; natural dialogue, not command software | P3 |
| REQ-PX-004 | voice | Text and voice share intent, entities, time, capability, resource, plan, execution, approval, outcome | P3 |
| REQ-PX-005 | intake | Natural-language objectives; no required API/connector/schema vocabulary | P4 |
| REQ-PX-006 | intake | Clarify only material ambiguity | P0 |
| REQ-PX-007 | text | Composer: assistant tone, not a trace; adaptive shape; no invented provider results | P0 |
| REQ-PX-008 | execute | Complete objectives (UNDERSTAND→LEARN); do not only explain | P1,P4 |
| REQ-PX-009 | execute | Strategy is not a second intelligence system | P0 |
| REQ-PX-010 | rw | Governed READ/WRITE; plan ≠ complete; API 200 ≠ business outcome | P0,P6 |
| REQ-PX-011 | artifact | Finished work bound to task/evidence/approval; description ≠ artifact | P5,P7 |
| REQ-PX-012 | progress | Meaningful progress; later computer is visible session under same governance | P5,P7 |
| REQ-PX-013 | continuity | One task across text, voice, desktop, mobile, workspace, workflow | P5 |
| REQ-PX-014 | speed | Measure ack / first text / first speech / first progress / first business result / complete / verified separately | P2,P3 |
| REQ-PX-015 | speed | Do not buy latency by weakening reasoning, accuracy, or governance | P2,M |
| REQ-PX-016 | learn | KF/entities/outcomes used; store-row is not “learned”; tenant-safe correctable | P4,P6 |
| REQ-PX-017 | accept | Journey eval on 12 points; tool invoke ≠ completed user work | EV |

### 7.2 Engineering phases

| ID | Phase | Requirement |
|----|-------|-------------|
| REQ-P0-001 | P0 | Preserve sealed compiled HMAC READ (HubSpot 25-deal canned) on every merge |
| REQ-P0-002 | P0 | Six shared contracts on every strategy |
| REQ-P0-003 | P0 | Document compatible release pair; identical SHAs not required |
| REQ-P1-001 | P1 | Skip LIVE when sealed/compiled READ owns the turn |
| REQ-P1-002 | P1 | LIVE cannot execute proposal → one-shot classical; no second tool-choice |
| REQ-P1-003 | P1 | Preserve pending-family, defer-SSE, bounded repair |
| REQ-P2-001 | P2 | Instrument sealed READ waterfall on current `/health` SHA |
| REQ-P2-002 | P2 | After waterfall, safest evidence-backed optimize in P2 bounds; no Composer rewrite; no HubSpot-only hack |
| REQ-P3-001 | P3 | PCM origin/turn-state; SAPI phrase speaks |
| REQ-P3-002 | P3 | `user_mic` barge-in during speaking remains |
| REQ-P3-003 | P3 | Do not globally suppress barge-in until STT final |
| REQ-P4-001 | P4 | Capability evidence plan before JIT/KF |
| REQ-P4-002 | P4 | CEO prompt: HubSpot/Ads Observation or explicit pending_auth; not internals-only |
| REQ-P4-003 | P4 | KF supplemental only |
| REQ-P5-001 | P5 | Workflow child Observation + parent plan/task id |
| REQ-P5-002 | P5 | No HMAC/Composer bypass on `tool_context_from_step` |
| REQ-P5-003 | P5 | Composer narrates when a human is waiting on a workflow |
| REQ-P6-001 | P6 | TOOL_SUCCESS is not plan bias |
| REQ-P6-002 | P6 | Consume labeled BUSINESS_IMPACT into `outcome_bias_section` |
| REQ-P7-001 | P7 | Computer/browser freeze; no second brain; no build this program |
| REQ-M-001 | M | n≥5 tier bake-off; prod default unchanged until Cesar signs |

### 7.3 Safety, deploy, program

| ID | Requirement |
|----|-------------|
| REQ-SF-001 | No HMAC / WRITE / OAuth / tenant / approval bypass |
| REQ-SF-002 | Isolated org only; never operator org kernel chat |
| REQ-SF-003 | No invented PASS, prices, Certified, Enable |
| REQ-SF-004 | No production WebRTC / Lane B / Computer Use without named human auth |
| REQ-OP-001 | Per-slice commit, required CI, authorized deploy, rollback, release pair |
| REQ-OP-002 | Ledger + gaps always current; no dropped requirements |
| REQ-OP-003 | After H0: continuous execution; per-phase re-approval not required |
| REQ-OP-004 | Material diversions recorded as decision exceptions; continue other work |
| REQ-OP-005 | Final implementation report only after all IDs processed |
| REQ-OP-006 | Independent acceptance audit is a **separate** later stage |

---

# SECTION 8 — TESTS, LIVE PROOF, SAFETY, DEPLOY, ROLLBACK

**Tests (every implementation slice):** focused unit on the changed contract; integration on the owning path (sealed READ **and** LIVE/clarify if both can reach the outcome); regression HubSpot canned 25-deal + WRITE-not-silent; no secret logging.

**Live verification:** isolated org only. Evidence = audit_events timestamp+action, conversation_id, plan_id, `/health` git_sha, Vercel prod SHA. Label `IMPLEMENTED_PROOF_PENDING` or `EXTERNALLY_BLOCKED` rather than fake PASS.

**Safety boundaries:** HMAC, PendingAction, `write_allowed`, tenant isolation, OAuth consent, no operator-org writes, no Computer Use build, no WebRTC enable, STA-312 exact entity match.

**Deployment:** existing main → Railway backend + Vercel frontend process. Known-good **release pair**. Contract compatibility. Do not wait for identical SHAs.

**Rollback:** revert the slice commit; Railway prior image; Vercel rollback candidate. P1/P3/P4/P5 behind flags where the spec already names them.

**Latency measures (must appear on live traces when the path runs):** acknowledgement, first useful text, first useful speech, first execution progress, first business result, completed work, verified outcome.

---

# SECTION 9 — FINAL PRODUCT-EXPERIENCE BENCHMARKS

Journeys (score all 12 §0.11 items). Classes per §0.11.

| ID | Journey | Program target class |
|----|---------|----------------------|
| EV-J-001 | Greeting | ANSWERED (keep shortcut) |
| EV-J-002 | Show my deals + only the large ones | COMPLETED then ANSWERED; faster first text after P2 opt |
| EV-J-003 | Send Sarah a summary | ANSWERED clarify; never silent WRITE |
| EV-J-004 | How is my business doing | COMPLETED or BLOCKED-honest |
| EV-J-005 | PCM “is Apollo connected” | COMPLETED spoken |
| EV-J-006 | HTTP Talk greeting | COMPLETED audio (keep) |
| EV-J-007 | Chat then workflow child | same plan_id Observation |
| EV-J-008 | Text then spoken same conversation | same task id |

Deferred Section 0 behaviors **remain tracked** (not satisfied by being out of this cycle): visible computer/browser execution; richer artifact productivity; physical-mic / driving hands-free LIVE_PROVEN; campaign asset factory.

**All requirements processed** = every catalog ID is in a terminal state.  
**Engineering complete** counts only `IMPLEMENTED_AND_VERIFIED` and `IMPLEMENTED_PROOF_PENDING`. `EXTERNALLY_BLOCKED` counts as engineering-complete **only** when implementation itself is complete and solely external proof is unavailable. `FAILED` and `NOT_IMPLEMENTED` **do not** count toward engineering completion.  
**Product accepted** = independent audit after the final implementation report (includes HUMAN_EXPERIENCE_PENDING items). Do not substitute the implementation report for that audit.

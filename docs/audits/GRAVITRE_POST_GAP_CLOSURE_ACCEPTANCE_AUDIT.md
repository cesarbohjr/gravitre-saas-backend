# Independent re-audit — post-gap-closure SHA `0191297f`

**Audit only. No implementation. Statuses are not inherited from the 426fce81 scorecard or the gap-closure directional recount.**

Captured: 2026-09-22T18:11Z–18:20Z  
Isolated org: `f07e57c0-1501-4000-8000-c04e57a00001`  
Evidence pack: `gravitre-evidence-closure-live.json`, `gravitre-pcm-closure-live.json`, `gravitre-reaudit-p4-extra-live.json`, `gravitre-gap-j007-j008-live.json`, plus this matrix.

---

## 1. Deployment truth

| Surface | Value |
|---|---|
| Implementation SHA | `0191297fa2eb4def8620a1b913a41314520d17bb` |
| origin/main | `0191297f` |
| local HEAD | `0191297f` |
| Railway `/health` | `0191297fa2eb4def8620a1b913a41314520d17bb` |
| Vercel production | same SHA; deployment `dpl_9rF4rQiPoMQb4Y2W6UAEtsN4N4Cu` |
| Required CI | PASS [run 35761237481](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35761237481) |
| LIVE / shadow | true |
| task_model_tier | `low` (production default unchanged) |
| `convergence_p1_single_selection_v1` | true |
| Release pair | backend + frontend both `0191297f` — compatible |

All acceptance evidence below is from this SHA.

---

## 2. 56-requirement recount

**PASS 25 · PARTIAL 25 · FAIL 2 · NOT_RUN 0 · EXTERNALLY_BLOCKED 2 · APPROVED_SCOPE_EXCEPTION 2**

Full rows: `gravitre-post-gap-closure-requirement-results.json`.

Prior independent (426fce81) was 22 / 12 / 13 / 5 / 2 / 2. That table is **not** this scorecard. Movement is from new live runs, not ledger copy.

---

## 3. P0 — HubSpot / non-regression — **PASS (quality)**

Run: `Show my deals.`  
Conversation `346fdc99-486e-4d5b-b750-9855e4c59f89`  
`tool.invoke.completed` `hubspot.deals.list` `provider_invoked=true`  
plan `960763e6-dcf4-4445-aac3-6f6582bd6650` step `read_sales_pipeline_health`  
Composer canned: “I found 25 deals in the connected CRM.”  
HMAC/preflight present in waterfall (`preflight` 261 ms compact; `provider` 1552 ms).  
Terminal: COMPLETED.

Quality remains **PASS**. First useful text **9062 ms**, complete **15168 ms**.

---

## 4. P1 — Single tool-selection — **PARTIAL**

Exact CEO/business prompt used in prior audits (`How is the business doing and what should I worry about?`):  
Conversation `fe585cb1-2d07-4545-b878-bb603862d8a6`  
No `inference.tool_completion`. Compiled HubSpot READ + pending_auth prose. HMAC preserved.

Related prompt `How is my company doing?` (same class, different needle):  
Conversation `888d620c-a19c-4986-a686-41af145b81c3`  
`unified_turn.live.completed` then `inference.tool_completion` + `agent.react.iteration`. Dual LIVE + ReAct selection. Internals-shaped clarify. First text **50980 ms**.

The live fix works on the **exact test phrase**. It does **not** hold for a near-synonym business prompt.

---

## 5. P2 — Latency — **PARTIAL**

Live waterfall **is present** on `runtime.turn_latency.critical_path` / `stages_compact` for HubSpot and CEO phrase.

Present: understanding, context-adjacent, memory checkpoint, compile, resource (mcp/engine), preflight, provider, Composer (`composer_start`), complete (journey `completion_ms`).

Absent as **named** marks: Observation, first SSE.

| Scenario | a7a0dd56 first | 426fce81 first | 0191297f first | 0191297f complete | Quality |
|---|---:|---:|---:|---:|---|
| Warm hi | 2092 | 4685 | 6329 | — | PARTIAL (warm 502) |
| Deals | 19931 | 29823 | **9062** | 15168 | PASS |
| Large? | 16787 | 21704 | 11224 | — | PASS |
| Sarah | 15756 | 28776 | 33743 | — | PASS clarify |
| CEO phrase | 31140 | 27062 | **9772** | 14916 | PASS this phrase |
| Company synonym | — | — | 50980 | 50980 | FAIL internals |

HubSpot TTFT **beats** both a7a0dd56 and 426fce81 **with** HMAC quality. Greeting cold is slower than a7. Sarah slower than both. Speed is not scored separately from correctness: deals **PASS**; CEO class **PARTIAL**.

---

## 6. P3 — Voice — **PARTIAL**

PCM/SAPI, phrase “Is Apollo connected”, `audio_origin=probe_pcm`, n=3 on SHA 0191297f.

| Run | assistant_text | audio_frames | interrupt_events | bot-interrupted |
|---|---|---:|---:|---|
| 0 | non-empty | **0** | 1 | after `tts.warmed` |
| 1 | non-empty | 60 | 1 | after `tts.warmed` |
| 2 (file) | loop narration | 5 | 1 | after `tts.warmed` |

Classification: **not purely benign warmup noise**. The remaining interrupt is a **race that can cancel or truncate legitimate TTS** (run 0: zero audio frames). Probe PCM still produces `user-started-speaking` during warmup.

- `probe_pcm` does **not** globally suppress all output (runs 1–2 spoke).
- It **can** still cut speech at warmup.
- `user_mic` barge-in: unit `test_p3_probe_pcm_does_not_barge_in_user_mic_does` **PASS**; physical mic **HUMAN_EXPERIENCE_PENDING**.
- Last spoken text was **loop narration**, not an Apollo connector answer. `tts_echo` was not observed masquerading as a user utterance in these traces.

Physical microphone: **HUMAN_TEST_PENDING**. Synthetic PCM is **not** full naturalness acceptance.

---

## 7. P4 — Business evidence — **PARTIAL**

| Prompt | Conv | Result |
|---|---|---|
| How is the business doing and what should I worry about? | `fe585cb1` | HubSpot 25 + GA/GSC pending_auth honest. Not internals-only. |
| How is my company doing? | `888d620c` | Agent/connector/workflow menu. Duplicate Composer. No HubSpot invoke. |
| Give me a business performance snapshot from connected systems. | `f46ab5d0` | Honest GA/GSC pending_auth. **No HubSpot.** |

This is still a **one-prompt special case** (CEO needles), not class-level business evidence.

---

## 8. P5 — Workflow same task — **FAIL (live)**

Conversation `31e8bfb7-0300-441d-a609-3a4943a57a97`

1. Chat objective: run **Canvas Write Governance Probe (no approval node)** — confirmation: reply **yes**.
2. User **yes**.
3. Reply: not a permitted action in this conversation.
4. `assistant_execute_workflow` **not** invoked.
5. Child Observation **none**.
6. `workflow_waiting` Composer **none** (execute path never entered).
7. Parent plan_id / child lineage **none**.
8. Terminal: BLOCKED / FAILED confirmation, not COMPLETED.

Wiring in code is **not** live completion. **P5 = FAIL** for acceptance. REQ-P5-003 PARTIAL (wired unused). REQ-P5-001 FAIL.

---

## 9. P6 — Outcome learning — **PARTIAL / H11 EXTERNALLY_BLOCKED**

TOOL_SUCCESS does not create business-plan bias (7d sample: no `business_metric_improved` from tool success).  
Positive BUSINESS_IMPACT consume: **EXTERNALLY_BLOCKED** (H11 label unavailable). Engineering is not failed solely for missing authorized label. Learning is **not** accepted without positive consume proof.

---

## 10. Model benchmark — **M = EXTERNALLY_BLOCKED**

Eval credentials unavailable. Production default remains `low` / gpt-5.4-mini. No inference that medium_high would be better.

---

## 11. Text experience — **PARTIAL**

| Probe | Result |
|---|---|
| Greeting | Natural cold; warm 502 flake |
| HubSpot | Canned 25, truthful |
| Follow-up | Clarifies large amount |
| CEO phrase | Grounded CRM + honest pending_auth |
| Company synonym | Internals vocabulary; duplicate text |
| WRITE | Clarifies Sarah; no write |
| Workflow confirmation | Card/text then **yes** refused |

Naturalness / reasoning / shape: ChatGPT-class on **canned CRM reads**; not on synonym CEO or workflow continue. Truthfulness of HubSpot count holds. Business usefulness **PARTIAL**. Latency **PARTIAL** (deals improved; other turns not).

---

## 12. Voice experience

| Slice | Verdict |
|---|---|
| Semantic parity (HTTP Talk vs text) | **PARTIAL** — HTTP Talk greeting/tool/J-008 share kernel; Pipecat PCM did not answer Apollo |
| Automated spoken delivery | **PARTIAL** — HTTP Talk audio; PCM interrupt race |
| Natural conversation readiness | **DOES_NOT_MEET** |
| Human device | **HUMAN_TEST_PENDING** |

---

## 13. Autonomous execution — **DOES_NOT_MEET**

Workflows still stop at confirmation. Observed classes:

- Greeting: ANSWERED (cold) / FAILED (warm 502)
- Deals / exact CEO: COMPLETED (READ)
- Sarah: ANSWERED (clarify)
- Company synonym: ANSWERED (unhelpful)
- Workflow: BLOCKED after yes
- No VERIFIED child execution

---

## 14. Task continuity — **PARTIAL**

| Path | Result |
|---|---|
| deals → large follow-up | Same `346fdc99`; clarify |
| text → HTTP Talk same conversation | `11b34c29` PASS (HTTP Talk) |
| chat → workflow child | FAIL |
| refresh/resume | NOT independently re-proven this pass |

---

## 15. Governance — **MEETS** (this SHA sample)

HMAC on sealed READ; PendingAction / WRITE safety (Sarah); tenant isolation `f07e57c0`; no operator-org kernel chat; no OAuth bypass (pending_auth stated); no invented 25-deal figure.

---

## 16. CI / four non-required jobs

Required CI: **PASS** on 0191297f.

Four previously failed non-required jobs **did not run on 0191297f** (schedule / path-filter). Last failures remain on **426fce81**. Classification: **stale / not-triggered**, not a proven 0191297f regression. Voice duplex **overlaps** spoken runtime in theme; live PCM already scores PARTIAL without that job.

---

## 17. Final scorecard

```
IMPLEMENTATION SHA: 0191297fa2eb4def8620a1b913a41314520d17bb
DEPLOYED BACKEND SHA: 0191297fa2eb4def8620a1b913a41314520d17bb
DEPLOYED FRONTEND SHA: 0191297fa2eb4def8620a1b913a41314520d17bb
REQUIRED CI: PASS (https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35761237481)
56 REQUIREMENTS:
PASS: 25
PARTIAL: 25
FAIL: 2
NOT_RUN: 0
EXTERNALLY_BLOCKED: 2
SCOPE_EXCEPTION: 2
P0: PASS (quality; HubSpot TTFT 9062ms HMAC 25)
P1: PARTIAL (exact CEO one-shot; synonym dual-select)
P2: PARTIAL (waterfall live; named Observation/first SSE missing; mixed TTFT)
P3: PARTIAL (PCM speaks inconsistently; warmup interrupt can zero audio)
P4: PARTIAL (exact phrase grounded; class not closed)
P5: FAIL (yes does not invoke workflow; no child Observation)
P6: PARTIAL (negative control); H11 EXTERNALLY_BLOCKED
M: EXTERNALLY_BLOCKED
P7: PASS (computer freeze held)
TEXT EXPERIENCE: PARTIAL
VOICE SEMANTIC PARITY: PARTIAL
VOICE AUTOMATED EXPERIENCE: PARTIAL
VOICE NATURAL / HUMAN DEVICE: HUMAN_TEST_PENDING
AUTONOMOUS EXECUTION: DOES_NOT_MEET
READ EXECUTION: MEETS
WRITE EXECUTION: MEETS (clarify / no unauthorized write)
TASK CONTINUITY: PARTIAL
BUSINESS EVIDENCE REASONING: PARTIAL
OUTCOME LEARNING: EXTERNALLY_BLOCKED (positive consume); PARTIAL engineering
LATENCY: PARTIAL
ARCHITECTURE CONVERGENCE: PARTIAL (one kernel; P1/P4 still needle-bound; P5 not live)
GOVERNANCE: MEETS
OPEN P0: none on HubSpot HMAC quality
OPEN P1: P5 live workflow invoke; P4/P1 class-level CEO; P3 interrupt race
HUMAN_EXPERIENCE_PENDING: physical microphone; Voice-C device
EXTERNAL BLOCKERS: H11 BUSINESS_IMPACT label; model bake-off credentials
DEFERRED SECTION 0: Computer Use; finished artifacts; real-device voice
CONVERGENCE PROGRAM ACCEPTED: NO
FULL SECTION 0 PRODUCT ACCEPTED: NO
READY FOR NEXT PRODUCT PHASE: NO
```

Stop for Cesar’s review. No Computer Use, no 3.0, no model-default change, no fixes in this audit.

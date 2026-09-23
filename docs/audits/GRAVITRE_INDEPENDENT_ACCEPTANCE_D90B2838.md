# Independent acceptance — production runtime `d90b2838`

**Audit only. No implementation. Statuses are not inherited from the implementation report, ledger, or SHA `0191297f` / `144550ff` / `72507653`.**

Captured: 2026-09-23T08:57Z–09:05Z  
Isolated org: `f07e57c0-1501-4000-8000-c04e57a00001`  
Evidence: `gravitre-independent-acceptance-d90b2838-live.json`, `gravitre-independent-acceptance-d90b2838-pcm.json`, `gravitre-independent-acceptance-d90b2838-requirement-results.json`

---

## 1. Deployment truth

| Surface | Value |
|---|---|
| Required runtime SHA | `d90b283800c1f446ee4181fd64ed5b8bfbb46030` |
| Railway `/health` | **`d90b2838`** @ `2026-09-23T08:57:29.758225Z` (reconfirmed at PCM `2026-09-23T09:03:07.460487Z`) |
| Git documentation tip | `b02db274` (ledger/docs only) — **not** used as runtime evidence |
| Vercel production (repo `gravitre-saas-backend`) | tip `b02db274` `dpl_6CzPzcvmv6nhWce9voYA2BE8Hze9`; prior READY `d90b2838` `dpl_5WXL5VVtEiQCq4CzESrMrTKhNN42` |
| Required CI (runtime SHA) | PASS [run 35834639673](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35834639673) |
| Railway verify (runtime SHA) | PASS [run 35834639759](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35834639759) |
| LIVE | `unified_turn_live_enabled=true` |
| `task_model_tier` | `low` |
| `convergence_p1_single_selection_v1` | true |
| Isolated org | `f07e57c0-…` only |

Frontend and backend SHAs **need not** be identical. Customer chat in this audit hit **Railway** `d90b2838`.

---

## 2. 56-requirement recount

**PASS 41 · PARTIAL 11 · FAIL 0 · NOT_RUN 0 · EXTERNALLY_BLOCKED 2 · APPROVED_SCOPE_EXCEPTION 2**

Rows: `gravitre-independent-acceptance-d90b2838-requirement-results.json`.

Prior independent (`0191297f`) was 25 / 25 / 2 / 0 / 2 / 2. Movement is from **this** live pack, not ledger copy.

---

## 3. P0 — HMAC READ / non-regression — **PASS**

`Show my deals.` conv `58abb039-a6f7-4e38-9698-ec6b8161c7a0`  
`tool.invoke.completed` `hubspot.deals.list` `provider_invoked=true` @ `2026-09-23T08:57:43.91009Z`  
plan `1f1993ab-…` step `read_sales_pipeline_health`  
Composer canned: “I found 25 deals in the connected CRM.”  
Waterfall: preflight, provider, observation, composer_start, first_sse present (`runtime.turn_latency.critical_path` @ `2026-09-23T08:57:44.175001Z`).  
First useful text **5045 ms**, complete **7240 ms**.

---

## 4. P1 — Single tool-selection — **PASS** (this SHA sample)

| Prompt | Conv | first_ms | Dual LIVE+ReAct | HubSpot |
|---|---|---:|---|---|
| How is the business doing and what should I worry about? | `780141eb-…` | 5734 | no (`react=[]`) | `hubspot.deals.list` @ `2026-09-23T08:57:52.912507Z` |
| How is my company doing? | `9709d2a7-…` | 7955 | no | @ `2026-09-23T08:58:04.253986Z` |
| How's the company doing? | `4ff31a89-…` | 5979 | no | same class |
| business performance snapshot | `bb0f79fc-…` | 6191 | no | same class |

No internals-only menu on these paraphrases. One compiled READ per turn.

---

## 5. P2 — Latency / waterfall / answer quality — **PASS (HMAC quality) / PARTIAL (product prose)**

Waterfall **is present** on this SHA. Named observation + first_sse appear in `stages_compact`.

HubSpot 25 + HMAC **PASS**. Answers remain **canned CRM counts**, not ChatGPT-class reasoning. Latency is scored with correctness: deals **PASS** HMAC; product-quality still **PARTIAL** under Section 0.

---

## 6. P3 — Voice — **PARTIAL**

Synth PCM into Pipecat (`gravitre-independent-acceptance-d90b2838-pcm.json`), SHA `d90b2838`, `physical_mic=false`.

| Phrase | assistant_text | audio_frames | interrupt_events |
|---|---|---:|---:|
| Is Apollo connected? | Yes, Apollo is connected and healthy. | 48 | 0 |
| What is the status of Apollo? | Yes, Apollo is connected and healthy. | 46 | 0 |
| Is HubSpot connected? | Yes, Hubspot is connected and healthy. | 55 | 0 |

Spoken content **addresses the request**. Repeatable in this n=3.  
Physical microphone / driving: **HUMAN_EXPERIENCE_PENDING**. Synth PCM is **not** full naturalness acceptance.

---

## 7. P4 — Business-evidence generalization — **PASS** (isolated-org grounding)

All four equivalent requests returned HubSpot 25 + honest GA/GSC `pending_auth`. Not internals-only. Not a substitute knowledge-file dump.

This is **grounded evidence class**, not ChatGPT-class business analysis.

---

## 8. P5 — Workflow — split dimensions

### 8a. Execution infrastructure (authorized noop fixtures) — **PASS**

| Fixture | Conv | `workflow.execute.completed` | plan_id | Observations |
|---|---|---|---|---|
| Alpha (noop) | `7cf6791b-d540-4ec2-9a34-1e01125338f7` | `2026-09-23T08:59:04.18209Z` | `fa58d43e-…` | prep+finish success |
| Beta (noop) | `9379be10-389c-429b-8f44-31949272e992` | `2026-09-23T08:59:32.941164Z` | `633295ed-…` | prep+finish success |

Composer: named workflow **finished**. Parent plan_id on child Observations. `assistant.execute_workflow` completed.

These fixtures **do not** prove complex autonomous business productivity or consequential provider-side WRITE.

### 8b. Consequential business / provider WRITE — **DOES_NOT_MEET**

CIM run `5f7f9ef6-…` remains `running` (historical EAGAIN leftover). Not mutated. Not terminal completion.  
No HubSpot/Apollo mutating WRITE completed in this audit.

### 8c. Approval / blocked honesty — **MEETS** (do not downgrade)

Canvas Write `cdda7de2-…` still `pending_approval`, trigger `manual`, `2026-09-21T18:35:31.623959Z`. **Not mutated.**  
Chat conv `246e9a0b-…` after yes: “Blocked: that workflow already has a run waiting for approval…” Composer kind `error`, not Done.

---

## 9. P6 — Outcome learning — **PASS (negative) / H11 EXTERNALLY_BLOCKED**

7d isolated `business*` audit sample empty. TOOL_SUCCESS did not invent BUSINESS_IMPACT in this sample.  
Positive labeled consume: **EXTERNALLY_BLOCKED** (H11).

---

## 10. M — **EXTERNALLY_BLOCKED**

No authorized eval credentials. Production remains `low`. No inference that a higher tier would pass Section 0.

---

## 11. P7 — **PASS**

No Computer Use product and no parallel intelligence runtime introduced in this cycle. Pre-existing `browser_agent_*` gap helpers are not a 3.0 rewrite. Freeze held.

---

## 12. Text / voice / execution vs Section 0

| Slice | Verdict |
|---|---|
| Text experience | **PARTIAL** — natural greeting; truthful canned CRM; not ChatGPT-class analysis |
| Voice semantic parity | **PARTIAL** — connector PCM matches; HTTP Talk greets; not physical |
| Voice automated | **PARTIAL** — synth answers this SHA |
| Voice natural / human device | **HUMAN_EXPERIENCE_PENDING** |
| Autonomous execution (noop infra) | **MEETS** fixtures |
| Autonomous execution (business WRITE) | **DOES_NOT_MEET** |
| READ execution | **MEETS** |
| WRITE execution | **MEETS** (clarify / no unauthorized write) |
| Task continuity | **PARTIAL** |
| Governance | **MEETS** this sample |
| Architecture | **MEETS** preserve+converge spine |

---

## 13. Open items

**Implementation defects (not new work in this audit):** CIM `5f7f9ef6` stuck `running`; leftover fixture `running` rows historically caused concurrency blocks.

**Human actions required:** Canvas `cdda7de2` approve/cancel/leave; CIM `5f7f9ef6` fail/cancel.

**External proof blockers:** physical mic; H11 BUSINESS_IMPACT label; model eval credentials; isolated GA/GSC pending_auth.

**Deferred Section 0:** Computer Use / visible browser; richer artifact productivity.

---

## 14. Final determinations

```
IMPLEMENTATION / RUNTIME SHA: d90b283800c1f446ee4181fd64ed5b8bfbb46030
DEPLOYED BACKEND SHA: d90b283800c1f446ee4181fd64ed5b8bfbb46030
DEPLOYED FRONTEND SHA: b02db274 (Vercel tip, docs-only; compatible, not identical)
REQUIRED CI: PASS (https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35834639673)
56 REQUIREMENTS:
PASS: 41
PARTIAL: 11
FAIL: 0
NOT_RUN: 0
EXTERNALLY_BLOCKED: 2
SCOPE_EXCEPTION: 2
P0: PASS
P1: PASS (this paraphrase class)
P2: PASS HMAC quality; PARTIAL product prose
P3: PARTIAL (synth correct; physical pending)
P4: PASS grounding class
P5 INFRA: PASS (Alpha/Beta terminals)
P5 BUSINESS WRITE: DOES_NOT_MEET
P5 APPROVAL: MEETS
P6: PASS negative; H11 EXTERNALLY_BLOCKED
M: EXTERNALLY_BLOCKED
P7: PASS
CONVERGENCE PROGRAM ACCEPTED: PARTIAL
FULL PRODUCT EXPERIENCE ACCEPTED: NO
READY FOR NEXT PRODUCT PHASE WITHOUT COMPROMISING CONVERGENCE ARCHITECTURE: YES — only if Cesar accepts PARTIAL and the next phase extends (does not replace) HMAC, Composer, PendingAction, task identity, and the existing workflow engine. Computer Use remains a later Section 0 item, not a remaining convergence FAIL.
```

Stop for Cesar’s review. No fixes in this audit.

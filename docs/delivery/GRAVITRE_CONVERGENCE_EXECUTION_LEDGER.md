# GRAVITRE CONVERGENCE EXECUTION LEDGER

**Authority:** `docs/audits/GRAVITRE_CONVERGENCE_SPEC.md`  
**Machine-readable:** `gravitre-convergence-execution-ledger.json`  
**Program status:** **IMPLEMENTATION RETURNED — NOT PRODUCT-ACCEPTED**  
**Implementation authorized:** true

This dashboard is the current view. Historical SHA evidence below does **not** certify current production.

---

## Current dashboard (2026-09-23)

| Field | Value |
|--------|--------|
| **Current production backend SHA** | `d90b283800c1f446ee4181fd64ed5b8bfbb46030` (`/health` 2026-09-23T08:21:49Z) |
| **Required CI** | **success** https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35834639673 |
| **Railway verify** | **success** https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35834639759 |
| **Independent re-audit SHA (frozen scorecard)** | `0191297fa2eb4def8620a1b913a41314520d17bb` — PASS 25 / PARTIAL 25 / FAIL 2 / **program NO** |
| **Product accepted** | **NO** — independent acceptance has not run on `d90b2838` |
| **Computer Use / 3.0 rewrite / model default** | not started; production tier still `low` |
| **Org** | isolated `f07e57c0-1501-4000-8000-c04e57a00001` only |

**Next executable:** independent acceptance on **`d90b2838`**. Do not grade `72507653` / `144550ff` / `1d1e78d4` / `bef7ac49` / `e0b77b95` as this release.

---

## Current-SHA live proof (`d90b2838`)

Isolated org. Not independent acceptance.

### P0 / P1 / P4 semantic class

`docs/audits/gravitre-semantic-paraphrase-live.json`

| Prompt | Conv | first useful text | Evidence |
|--------|------|------------------:|----------|
| How is my company doing? | `2846e08e-…` | 7592 ms | `tool.invoke.completed` `hubspot.deals.list` @ `2026-09-23T08:17:47.503988Z` — 25 deals + GA/GSC pending_auth |
| How's the company doing? | `8aa0bd09-…` | 5798 ms | `hubspot.deals.list` @ `2026-09-23T08:17:57.241677Z` |
| business performance snapshot | `d3c44f58-…` | 7127 ms | `hubspot.deals.list` @ `2026-09-23T08:18:08.152101Z` |

No internals menu. One HubSpot compiled READ per turn. Honest GA/GSC pending_auth.

### P3 voice (synthesized PCM)

`docs/audits/gravitre-pcm-closure-live.json` — SYNTHESIZED_PCM, not a physical mic.

| Phrase (STT) | Spoken assistant_text | audio_frames |
|--------------|------------------------|-------------:|
| `Is Apollo connected?` | `Yes, Apollo is connected and healthy.` | 50 |
| `is Apollo connected.` | `Yes, Apollo is connected and healthy.` | 53 |
| `Can you check whether Apollo is connected?` | `Yes, Apollo is connected and healthy.` | (same class) |
| `What is the status of Apollo?` | `Yes, Apollo is connected and healthy.` | (same class) |
| `Is HubSpot connected?` | `Yes, Hubspot is connected and healthy.` | (same class) |

Physical microphone / driving: **HUMAN_EXPERIENCE_PENDING**.

### P5 workflow

Confirm path works. Started ≠ completed. A child step ≠ terminal completion.

Isolated-org noop fixtures **Alpha** / **Beta** are labeled placeholder test workflows, not a customer catalog. **(b) scaffold.**

| Journey | Result | Pointer |
|---------|--------|---------|
| Alpha | **Terminal completed** | conv `3d011b1f-…`; `workflow.execute.completed` @ `2026-09-23T08:16:43.024146Z`; prep+finish `workflow.child.observation` plan `643d1791-…`; Composer “ran and finished” |
| Beta | **Terminal completed** | conv `c2feba24-…`; `workflow.execute.completed` @ `2026-09-23T08:13:44.934553Z`; prep+finish Observations plan `fabb7b18-…`; Composer “started and finished” |
| J007 Beta repeat | **Terminal completed** | conv `6b8bc07d-…`; prep+finish Observations plan `d3fe5e0b-…`; `tool.invoke.completed` `assistant.execute_workflow` @ `2026-09-23T08:20:55.162219Z` |
| Canvas Write | **Legitimately blocked**; not mutated | conv `7ce0ce19-…`; run `cdda7de2-…` still `pending_approval` trigger `manual` since `2026-09-21T18:35:31.623959Z`; chat: approve/cancel first |
| Sales Automation | **Honest pending_approval** | conv `85ef1f0d-…`; `workflow.execute.pending_approval` @ `2026-09-23T08:19:15.742858Z`; “still waiting for approval, so nothing has completed yet” |
| Sarah WRITE | Clarify, no WRITE | conv `a481e417-…` — which Sarah / what summary |
| J008 text→HTTP Talk | Continuity | conv `1bb45907-…` spoken_first_text_ms=161 audio_ms=164 |
| CIM `5f7f9ef6` | Still **running** leftover | **human:** fail or cancel. Not mutated. Historical scan Observation @ `2026-09-23T01:51:32.072508Z` is **not** terminal completion |

### P6

TOOL_SUCCESS still not plan bias (unit). H11 BUSINESS_IMPACT **EXTERNALLY_BLOCKED**.

### Required CI

- Required CI **success** https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35834639673
- Railway backend production **success** https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35834639759

Four non-required jobs: not weakened (Click Audit, voice duplex browser, Connector Verified Writes, Credential DB Bypass).

---

## Engineering implementation (this return)

- Chat workflow execute: `force_inline=True`, trigger_type **`api`**, `source=assistant_chat` in parameters.
- Thin graph nodes overlay bound `steps[].metadata.agent_id` at compile time (class-level, not CIM-specific).
- Graph path emits `workflow.child.observation` when parent `plan_id` is present.
- Dedicated `gravitre-async-bridge` loop; `call_with_resource_retry` on graph nodes, graph batches, and `_finalize_run` for wrapped `[Errno 11] Resource temporarily unavailable`.
- Connector-status paraphrases: whole-utterance `Is X connected?/.`, `Can you check whether X is connected?`, `What is the status of X?`. Job-shaped “check that my Google Ads account is actually connected” stays operator-task.
- `pending_approval` returns `workflow_pending_approval` (not canned Done).

---

## Deferred / blocked (honest)

| Item | Status |
|------|--------|
| Independent product acceptance | **NOT RUN** on `d90b2838` |
| Physical mic / driving | HUMAN_EXPERIENCE_PENDING |
| H11 labeled BUSINESS_IMPACT | EXTERNALLY_BLOCKED |
| Eval-key bake-off / model default change | EXTERNALLY_BLOCKED / not authorized |
| Computer Use | not built |
| Canvas Write `cdda7de2` | **human:** approve, cancel, or leave pending (`pending_approval`, trigger `manual`, `2026-09-21T18:35:31.623959Z`) |
| CIM run `5f7f9ef6` stuck `running` after EAGAIN | **human:** fail/cancel that run (not Canvas); do not treat as completed |
| Sales Automation / F6 approval floor | Honest pending; do not auto-approve |
| Isolated GA/GSC | pending_auth — not an engineering failure |
| CIM terminal completion on this SHA | Blocked by leftover `running` run until human disposition |

---

## Historical SHA evidence (do not certify current prod)

| SHA | What it proved | What it must not be used for |
|-----|----------------|------------------------------|
| `72507653` | F6 honesty; CIM child scan | Current production |
| `1d1e78d4` / `bef7ac49` / `e0b77b95` | EAGAIN iteration; partial Alpha/Beta | Current production |
| `0191297f` | Independent re-audit pack | Current production |
| `144550ff` | Earlier paraphrase/PCM/HubSpot | Final release |

---

## Product acceptance

Not self-declared. Binding standard remains Section 0. A tool invocation is not completed work. A spoken narration is not an answer. A confirmation card is not execution.

## Terminal-state rules

IMPLEMENTED_AND_VERIFIED · IMPLEMENTED_PROOF_PENDING · EXTERNALLY_BLOCKED · FAILED · NOT_IMPLEMENTED · APPROVED_SCOPE_EXCEPTION

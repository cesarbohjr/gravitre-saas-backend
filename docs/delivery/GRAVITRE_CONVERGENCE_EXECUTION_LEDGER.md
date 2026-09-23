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
| **Current production backend SHA** | `144550ffc1459a93391890c0fd92844946de7ea7` (`/health` 2026-09-23T01:45:01Z) |
| **Required CI** | **success** https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35806536829 |
| **Railway verify** | **success** https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35806536697 |
| **Independent re-audit SHA (frozen scorecard)** | `0191297fa2eb4def8620a1b913a41314520d17bb` — PASS 25 / PARTIAL 25 / FAIL 2 / **program NO** |
| **Product accepted** | **NO** — independent acceptance has not run on `144550ff` |
| **Computer Use / 3.0 rewrite / model default** | not started; production tier still `low` |
| **Org** | isolated `f07e57c0-1501-4000-8000-c04e57a00001` only |

**Next executable:** independent acceptance on **`144550ff`**. Do not grade `d5432790` / `0191297f` / `54c9e7a1` as this release.

---

## Current-SHA live proof (`144550ff`)

Isolated org. Not independent acceptance.

### P0 / P1 / P4 semantic class

`docs/audits/gravitre-semantic-paraphrase-live.json`

| Prompt | Conv | first useful text | Evidence |
|--------|------|------------------:|----------|
| How is my company doing? | `4a6617b7-…` | 10215 ms | `tool.invoke.completed` `hubspot.deals.list` @ `2026-09-23T01:57:30.151277Z` — 25 deals + GA/GSC pending_auth |
| How's the company doing? | `e1c510ea-…` | 7501 ms | `hubspot.deals.list` @ `2026-09-23T01:57:42.375545Z` |
| business performance snapshot | `8c2b7ba3-…` | 22247 ms | `hubspot.deals.list` @ `2026-09-23T01:58:09.977811Z` |

No internals menu. One HubSpot compiled READ per turn. Honest GA/GSC pending_auth.

### P3 voice (synthesized PCM)

`docs/audits/gravitre-pcm-closure-live.json` — SYNTHESIZED_PCM, not a physical mic.

| Phrase (STT) | Spoken assistant_text | audio_frames |
|--------------|------------------------|-------------:|
| `Is Apollo connected?` | `Yes, Apollo is connected and healthy.` | 53 |
| `is Apollo connected.` | `Yes, Apollo is connected and healthy.` | (same class) |
| `Can you check whether Apollo is connected?` | `Yes, Apollo is connected and healthy.` | (same class) |
| `What is the status of Apollo?` | `Yes, Apollo is connected and healthy.` | (same class) |
| `Is HubSpot connected?` | `Yes, Hubspot is connected and healthy.` | (same class) |

Physical microphone / driving: **HUMAN_EXPERIENCE_PENDING**.

### P5 workflow

Confirm path works. Started ≠ completed. Audio ≠ answer.

| Journey | Result | Pointer |
|---------|--------|---------|
| CIM NL → yes | First child **scan succeeded** with Observation | conv `d8c721d8-…`; `workflow.child.observation` scan `success=true` `hmac_bypass=false` `execution_mode=graph` @ `2026-09-23T01:51:32.072508Z` plan `7b6d33d8-…` |
| CIM after scan | Second step hit `[Errno 11] Resource temporarily unavailable`; Composer error (not fake Done) | `tool.invoke.failed` @ `2026-09-23T01:51:32.216409Z`; run `5f7f9ef6-…` still **running** |
| Canvas Write | **Legitimately blocked**; honest blocker | conv `599f8eaa-…`; awaiting approval `cdda7de2-…`; chat: approve/cancel that run first. **Not mutated.** |
| F6 / Sales Automation | Approval floor `pending_approval` | F6 conv `37f5901d-…` `policy.override.approval_floor_applied` @ ~`2026-09-23T01:52:06Z`. Chat still said **Done — started** on this SHA — honesty patch not yet this `/health`. |
| Sarah WRITE | Clarify, no WRITE | conv `450b0319-…` `2026-09-23T02:03Z` — which Sarah / what summary |
| J008 text→HTTP Talk | Continuity | conv `dab6f643-…` spoken_first_text_ms=205 audio_ms=208 |

### P6

TOOL_SUCCESS still not plan bias (unit). H11 BUSINESS_IMPACT **EXTERNALLY_BLOCKED**.

### Required CI

- `144550ff` required CI **success** https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35806536829
- Railway backend production **success** https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35806536697

Four non-required jobs: not weakened (Click Audit, voice duplex browser, Connector Verified Writes, Credential DB Bypass).

---

## Engineering implementation (this return)

- Chat workflow execute: `force_inline=True`, trigger_type **`api`**, `source=assistant_chat` in parameters.
- Thin graph nodes overlay bound `steps[].metadata.agent_id` at compile time (class-level, not CIM-specific).
- Graph path emits `workflow.child.observation` when parent `plan_id` is present.
- Connector-status paraphrases: whole-utterance `Is X connected?/.`, `Can you check whether X is connected?`, `What is the status of X?`. Job-shaped “check that my Google Ads account is actually connected” stays operator-task.

---

## Deferred / blocked (honest)

| Item | Status |
|------|--------|
| Independent product acceptance | **NOT RUN** on `144550ff` |
| Physical mic / driving | HUMAN_EXPERIENCE_PENDING |
| H11 labeled BUSINESS_IMPACT | EXTERNALLY_BLOCKED |
| Eval-key bake-off / model default change | EXTERNALLY_BLOCKED / not authorized |
| Computer Use | not built |
| Canvas Write `cdda7de2` | **human:** approve, cancel, or leave pending (`pending_approval`, trigger `manual`, `2026-09-21T18:35:31Z`) |
| CIM run `5f7f9ef6` stuck `running` after EAGAIN | **human:** fail/cancel that run (not Canvas); do not treat as completed |
| F6 / Sales Automation approval floor vs canned “Done — started” | honesty patch in tip (pending_approval is not completion); re-verify after next Railway SHA |
| Isolated GA/GSC | pending_auth — not an engineering failure |
| Two fully successful end-to-end workflows to terminal completed | CIM scan Observation only; second authorized workflows hit approval floor or name ambiguity |

---

## Historical SHA evidence (do not certify current prod)

| SHA | What it proved | What it must not be used for |
|-----|----------------|------------------------------|
| `0191297f` | Independent re-audit pack `docs/audits/GRAVITRE_POST_GAP_CLOSURE_ACCEPTANCE_AUDIT.md` | Current production |
| `54c9e7a1` | Paraphrases, PCM audio frames, HubSpot ~6.5s | Final release; P3 answer quality; P5 execute |
| `3773cbf5` | Yes reached `tool.invoke.requested`; confirm composed as error; execute 409 | Current execute/voice |
| `e1ef6c27` / `8bb99a6c` | Paraphrases + STT period parse | Skip if superseded by `d5432790` runtime |

---

## Product acceptance

Not self-declared. Binding standard remains Section 0. A tool invocation is not completed work. A spoken narration is not an answer. A confirmation card is not execution.

## Terminal-state rules

IMPLEMENTED_AND_VERIFIED · IMPLEMENTED_PROOF_PENDING · EXTERNALLY_BLOCKED · FAILED · NOT_IMPLEMENTED · APPROVED_SCOPE_EXCEPTION

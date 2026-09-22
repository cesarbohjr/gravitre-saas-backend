# GRAVITRE CONVERGENCE EXECUTION LEDGER

**Authority:** `docs/audits/GRAVITRE_CONVERGENCE_SPEC.md`  
**Machine-readable:** `gravitre-convergence-execution-ledger.json`  
**Program status:** **IMPLEMENTATION RETURNED — NOT PRODUCT-ACCEPTED**  
**Implementation authorized:** true

This dashboard is the current view. Historical SHA evidence below does **not** certify current production.

---

## Current dashboard (2026-09-22)

| Field | Value |
|--------|--------|
| **Current production backend SHA** | `d543279021678f4275f28696217a90eeca96c08a` (`/health` 2026-09-22T22:30:36Z) |
| **Tip (tests-only follow-up)** | `fb497ad5` (does not change runtime vs `d5432790`) |
| **Independent re-audit SHA (frozen scorecard)** | `0191297fa2eb4def8620a1b913a41314520d17bb` — PASS 25 / PARTIAL 25 / FAIL 2 / **program NO** |
| **Product accepted** | **NO** — independent acceptance has not run on `d5432790` |
| **Computer Use / 3.0 rewrite / model default** | not started; production tier still `low` |
| **Org** | isolated `f07e57c0-1501-4000-8000-c04e57a00001` only |

**Next executable:** independent acceptance on **`d5432790`** (or later runtime SHA if CI tip is redeployed). Do not grade `54c9e7a1` / `3773cbf5` / `0191297f` as this release.

---

## Current-SHA live proof (`d5432790` / paraphrases also on `8bb99a6c` same series)

Isolated org. Not independent acceptance.

### P0 / P1 / P4 semantic class (`8bb99a6c`)

`docs/audits/gravitre-semantic-paraphrase-live.json`

| Prompt | Conv | first useful text | Evidence |
|--------|------|------------------:|----------|
| How is my company doing? | `6ed95a51-…` | 10813 ms | `tool.invoke.completed` `hubspot.deals.list` @ `2026-09-22T22:11:35.653914Z` — 25 deals + GA/GSC pending_auth |
| How's the company doing? | `65b0fd69-…` | 8857 ms | `hubspot.deals.list` @ `2026-09-22T22:11:48.919597Z` |
| business performance snapshot | `1fe87cb1-…` | 6844 ms | `hubspot.deals.list` @ `2026-09-22T22:12:00.658858Z` |

No internals menu. Equivalent CEO/ops class → HubSpot compiled READ. **Not** the 6.5s HubSpot result from `54c9e7a1`.

Waterfall (same class, `runtime.turn_latency.critical_path` @ `2026-09-22T21:46:16.818175Z` on `e1ef6c27`): `observation` and `first_sse` present; client first-text still ~7–11s; UNDERSTANDING and CONNECTED_INTEGRATIONS remain large on some turns.

### P3 voice (`d5432790`)

`docs/audits/gravitre-pcm-closure-live.json` — SYNTHESIZED_PCM, not a physical mic.

| Run | STT | Spoken assistant_text | interrupt_events | audio_frames |
|-----|-----|------------------------|-----------------:|-------------:|
| 1 | `is Apollo connected.` | `Yes, Apollo is connected and healthy.` | 0 | 53 |
| 2 | `is Apollo connected.` | `Yes, Apollo is connected and healthy.` | 0 | 53 |

Physical microphone / driving: **HUMAN_EXPERIENCE_PENDING**.

### P5 workflow (`d5432790`)

Confirm path works. `tool.invoke.requested` is **not** completion.

| Journey | Result | Pointer |
|---------|--------|---------|
| Confirm CIM | Asks for **yes** | conv `292f8964-…` |
| Yes on CIM | Run **created and started**, step **failed** (agent step missing `agent_id`) | `workflow.execute.step_failed` scan / `workflow.execute.failed` @ `2026-09-22T22:12:56.965448Z` (prior CIM) and again on `292f8964-…`. Composer: incomplete configuration — **not** a fake Done. Child Observation **not** produced (step never completed). |
| Canvas Write | **Legitimately blocked** | Active `pending_approval` run `cdda7de2-…` trigger `manual` since `2026-09-21T18:35:31Z`. Chat yes 409 / in-progress. **Human choice required:** approve, cancel, or leave that run. |
| F6 entity_get | Chat yes created run then **approval floor** `pending_approval` | conv `695d5512-…` — `policy.override.approval_floor_applied` + `workflow.execute.pending_approval`. Chat confirm ≠ workflow approval. |

### P6

TOOL_SUCCESS still not plan bias (unit). H11 BUSINESS_IMPACT **EXTERNALLY_BLOCKED**.

### Required CI

- `8bb99a6c` required CI **success** https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35790125093  
- `d5432790` required CI **failure** (narration unit expected old getConnectorStatus progress speech) https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35791843100  
- `fb497ad5` test fix pushed — required CI must be confirmed green before treating tip as certified.

Four non-required jobs: not weakened (Click Audit, voice duplex browser, Connector Verified Writes, Credential DB Bypass).

---

## Engineering implementation (this return)

- Chat workflow execute: `force_inline=True`, trigger_type **`api`** (DB check allows `manual|schedule|rollback|webhook|api|hubspot`), `source=assistant_chat` in parameters.
- Drain unstarted **running** assistant/api chat jobs only — never `pending_approval`.
- Failed / incomplete runs: Composer **error**, pending kept when resumable.
- Connector-status: not operator-task; STT trailing `.` matches; skip getConnectorStatus progress TTS.

---

## Deferred / blocked (honest)

| Item | Status |
|------|--------|
| Independent product acceptance | **NOT RUN** on `d5432790` |
| Physical mic / driving | HUMAN_EXPERIENCE_PENDING |
| H11 labeled BUSINESS_IMPACT | EXTERNALLY_BLOCKED |
| Eval-key bake-off / model default change | EXTERNALLY_BLOCKED / not authorized |
| Computer Use | not built |
| Canvas Write pending_approval `cdda7de2` | **human disposition required** |
| CIM / F6 as golden execute-to-Observation | CIM config incomplete; F6 approval floor |

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

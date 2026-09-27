# Section 0 assurance package

**Date:** 2026-09-27  
**Scope:** Verification and acceptance assurance only. No new product capabilities.  
**Isolated org:** `f07e57c0-1501-4000-8000-c04e57a00001`  
**Tree at this pass:** `4ee5cb174094d373818c59949d8aa9785e0a1730` plus the one-line `map_stage("observation")→PROVIDER` lock in this commit.  
**Product Experience Contract:** **not fully accepted.**

Do not transfer evidence across SHAs. Each live row is bound to the SHA that served it.

This file is the authoritative Section 0 matrix for the current hold. The older surface table in `gravitre-product-acceptance-matrix.md` remains historical detail.

---

## 1. What is fully accepted?

Nothing at the full Section 0 bar (`0.11` twelve-point journey + `0.13` text-or-voice business objective across devices).

Closed **capability slices** (preserve; do not reopen):

| Slice | Class | SHA | Live ids |
|---|---|---|---|
| Class C governed HubSpot READ | LIVE_API_PROVEN | `c29f12cb451fe75db6f657c0534dab8f3a36f201` | conv `b30ba508-…` first useful **4114 ms** / completion **6125 ms** |
| Catalog search | LIVE_API_PROVEN | `158c43eb9e65d66e0329b7d51410518a34f07323` | conv `7d6901ef-…` request `66c0e4eb-…` first useful **4803 ms** / completion **7615 ms** |
| Computer Use first navigation | LIVE_API_PROVEN | `bcff57021460cdf27da8cc5e88083b49d19d205c` | conv `4ada3849-…` Observation `187f041c-…` first useful **4304 ms** / completion **4760 ms** |
| Persisted Computer Use follow-up | LIVE_API_PROVEN | `bcff5702…` (same conversation) | follow-up **1814 ms**; title **2666 ms**; `obs_count=1` |
| Finished artifacts (API) | LIVE_API_PROVEN | `f522a717…` table; `b6a9722c…` interact follow-up | conv `fb03f3fe-…` Observation `fd95772b-…` |
| Governed connector WRITE lifecycle | LIVE_API_PROVEN / LIVE_VOICE_PROVEN (PCM, not mic) | `dd576514…` HTTP; `1f548ca8…` / `0b2e42c3…` PCM | HubSpot `278972733388`, `279209311173`, `279246127081` |
| CU interact **mechanics** | CI_PROVEN + LIVE_API_PROVEN | `ecb86dcfa2c87c42c8bbfbb8638415a7db7924e9` | httpbin only — **do not repeat** |

---

## 2. What is CI_PROVEN?

Targeted regression 2026-09-27 (this tree, local): **302 passed** across the closed-path + negative-path files listed in §10.

GitHub Actions:

| SHA | Workflow | Result | URL |
|---|---|---|---|
| `c29f12cb…` | CI | success | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36187356918 |
| `7ac66c36…` | CI | success | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36116044917 |
| `ecb86dcf…` | CI | success | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36218136434 |
| `b6a9722c…` | CI | success | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36226281760 |
| `9fcaa89c…` | CI | success | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36229510637 |
| `4ee5cb17…` | Railway backend production | success | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36306934992 |
| `4ee5cb17…` | CI Backend (pytest) | **1 failed / 6730 passed** | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36306935027 |

**CI finding (this pass):** `test_p2_observation_and_first_sse_marks` failed because `map_stage("observation")` fell through to `OBSERVATION` instead of `PROVIDER`. `_mark("observation")` is used on compiled short-circuits; `STAGE_CANONICAL` only listed `observation_persist`. One-line alias added. Not a product-behavior change. Same Backend pytest failure was already red on `bcff5702`, `824197bc`, and `524aed29`.

Catalog SHA `158c43eb` Railway deploy: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36274811849. Push `CI` workflow for that SHA was not in the first GitHub API page; do not invent a pytest run URL.

---

## 3. What is LIVE_API_PROVEN?

HTTP `/api/assistant/chat` (often `spoken_mode`) on production, isolated org, with conversation / plan / Observation ids:

- Governed READ contact-count: `f7d13fba…` conv `278173be-…` plan `bef07e98-…` (`hubspot.contacts.search` total 57 @ `2026-09-24T22:04:31Z`). Also Class C on `c29f12cb…` conv `b30ba508-…`.
- Catalog search: `158c43eb…` conv `7d6901ef-…`. Tools none. WRITE rows labeled not executed. `searchKnowledgeBase` false. **That SHA did not persist `execution_path` / `work_artifacts` on the live JSON.** Artifact binding is later (`824197bc`) and is **CI_PROVEN, not a new LIVE_API re-run**.
- Computer Use READ + follow-up: `7ac66c36…` continuity; latency band `bcff5702…` conv `4ada3849-…` Observation `187f041c-…`.
- Connector WRITE: `dd576514…` contact `278972733388`; identity follow-up `0b879ec4…` / `279246127081`.
- Proactive attention: `4a1e84e9…` conv `5cfc0c14-…` `notice_count=2`, `write_allowed=false` @ `2026-09-24T15:25:22Z`.
- PCM WRITE (not physical mic): `1f548ca8…` / `0b2e42c3…` conv `59120b14-…` / `74ad31c7-…`.

---

## 4. What is harness-only?

Command OS `/e2e/execution-result?scenario=computer_browser_read` and `catalog_search`. Local Playwright 2 passed 2026-09-27. **Not LIVE_UI_PROVEN.** Not signed-in `/ai`.

---

## 5. What still needs owner-live UI?

Owner-live Plus/UI = **PENDING**. Command OS signed-in presentation = **not LIVE_UI_PROVEN**.

---

## 6. What still needs human physical-mic testing?

Physical mic = **HUMAN_EXPERIENCE_PENDING**. Synthetic PCM is not this gate. Procedure remains in `gravitre-product-acceptance-matrix.md`.

---

## 7. What is blocked on an authorized external target?

Real-world Computer Use WRITE = **BLOCKED_NO_AUTHORIZED_TARGET**. Interact matcher remains `httpbin.org` only. No synthetic target. No customer/prod mutation during this pass.

HubSpot probe cleanup still needs Cesar: `278972733388`, `279209311173`, `279246127081`.

---

## 8. What is intentionally deferred?

- Campaign / design asset factory (spec §0.6).
- Production “show the work” checklist stream (`gravitre-product-experience-contracts.md`).
- Progress SSE as a **latency** claim (`first_progress_ms` null on spoken CU probes). UX-only.

`GRAVITRE_CONVERGENCE_GAPS_AND_EXCEPTIONS.md` GAP-007 still says “visible computer / richer artifacts / no Computer Use.” That row is **historical (2026-09-22 cycle)**. Later SHAs proved CU READ + artifacts on API. Do not treat GAP-007 as the current capability truth.

---

## 9. Known-good baseline SHAs

Do not collapse to one SHA.

| Role | SHA |
|---|---|
| Current hold tree | `4ee5cb17…` + observation-map alias in this commit |
| CU latency LIVE | `bcff57021460cdf27da8cc5e88083b49d19d205c` |
| Catalog search LIVE | `158c43eb9e65d66e0329b7d51410518a34f07323` |
| Class C READ LIVE | `c29f12cb451fe75db6f657c0534dab8f3a36f201` |
| CU READ continuity LIVE | `7ac66c362e342cb58108d088a3744b3c78c1a341` |
| CU interact mechanics LIVE | `ecb86dcfa2c87c42c8bbfbb8638415a7db7924e9` |
| Listing table artifact LIVE | `f522a7179707d40cf768b45b4c78dc8ffc466622` |
| Command OS table presentation CI | `9fcaa89c45409baf1dadeafaa2c6891d268730c2` |
| HTTP governed WRITE + identity | `dd576514998072a1603a29fa6ec55e4e88a80398`, `0b879ec4577965ca3029bacd13e54d218192c0f6` |
| PCM WRITE (not mic) | `1f548ca8acf411485f95111e07bf2f8d131fce2f`, `0b2e42c35d52b95e6083dba6e2e5da962f996ed8` |
| Catalog/entity artifact **code** (not LIVE re-proof) | `824197bcabd648413e7bead05f055a6cf7de63af`, `524aed29c25495be1e10cf6f5b55169c000ca2d9` |

---

## 10. Regression tests per capability

### Closed critical paths (this pass)

| Path | Tests | Local 2026-09-27 |
|---|---|---|
| A Governed provider READ | `test_platform_execution_3_0_h_entities.py`, `test_f2_read_repair.py`, `test_operational_read_execution.py`, `test_p0_live_read_grounding.py` | included in 302 |
| B Catalog search | `test_jit_tool_skills.py`, `test_canonical_cognitive_ingress.py`, `test_response_composer.py` | included |
| C–D Computer Use READ / follow-up | `test_computer_browser_read_turn.py` | included |
| E Governed CU interact | `test_computer_browser_interact_turn.py` (HMAC, no HubSpot, httpbin-only lock) | included |
| F Durable artifacts | `test_durable_work_session.py`; vitest `canonical-artifact-presentation.test.ts` (1 passed) | included |
| G Connector WRITE lifecycle | `test_action_lifecycle.py`, `test_phase_f1_write_preflight.py`, `test_governed_write_compile.py`, `test_platform_execution_3_0_i_spoken_write.py` | included |
| Latency envelope (recorded live JSON) | `test_section_0_latency_envelope.py` | 3 passed |

### Negative paths

| Case | Status | Test / evidence |
|---|---|---|
| Disconnected provider | CI_PROVEN | `test_connector_status_reply.py` |
| Unavailable ActionSpec / HMAC missing | CI_PROVEN | `test_phase_f1_write_preflight.py` `test_invoke_write_without_hmac_does_not_call_provider`; interact `test_interact_confirm_without_hmac_does_not_submit` |
| Ambiguous WRITE / approval | CI_PROVEN + LIVE PCM | `test_platform_execution_3_0_i_spoken_write.py` (`yes wait`); live “Yes. Maybe.” on PCM WRITE |
| Duplicate confirmation | CI_PROVEN + LIVE | `test_action_lifecycle.py` `test_duplicate_confirm_skips_second_invoke`; PCM “I won’t create a duplicate.” |
| Expired/stale PendingAction | CI_PROVEN | `recover_orphaned_executing` in `test_action_lifecycle.py` |
| Provider error | CI_PROVEN | `test_hubspot_error_classification.py` |
| Browser selector miss | CI_PROVEN | `test_computer_browser_read_turn.py` skip-empty `count()==0` |
| Interrupted browser session | CI_PROVEN (partial) | isolated `new_context`; **not** a LIVE crash-recovery of Chromium mid-goto |
| Missing persisted visits / artifact | CI_PROVEN | CU follow-up without evidence; `reconstruct_execution_result` None without artifacts |
| Stale conversation resume | CI_PROVEN | listing/CU resume `provider_reinvoked=false` |
| Cross-tenant | CI_PROVEN | `test_phase_f1_read_preflight.py`, `test_conversation_write_guard.py`, `test_platform_execution_3_0_h_entities.py` |
| Unauthorized WRITE | CI_PROVEN | HMAC + awaiting_confirm |
| Unsupported CU WRITE target | CI_PROVEN | `test_interact_write_stays_httpbin_only_until_authorized_target` |

No real external mutations in this pass.

---

## 11. What would revoke Section 0 slice acceptance?

- Class C / catalog / CU first-nav recorded live JSON edited so first useful **> 8s** or completion **> 12s**, or a new live probe on those paths in the **10–30s** band.
- Catalog executing WRITE or calling `searchKnowledgeBase`.
- CU READ using httpx as the session, or follow-up replaying Playwright (`obs_count` increment).
- HMAC bypass, auto high-risk WRITE, duplicate invoke, or cross-tenant leakage.
- Invented success / silent mutation.
- Second artifact model in Command OS.
- Claiming LIVE_UI_PROVEN or physical-mic LIVE without Cesar’s owner session / device.
- Claiming real-world CU WRITE without an authorized isolated target.

---

## Section 0 requirement matrix

| Requirement | Status | Class | SHA | CI | Live | Artifact | Tests | Limitation |
|---|---|---|---|---|---|---|---|---|
| 0.1 Natural intake | PARTIAL | LIVE_API_PROVEN | `c29f12cb`, `158c43eb`, `bcff5702` | see §2 | listing/catalog/CU prompts | — | listing + catalog + CU intent tests | CEO/ops still need connected sources; KF must not substitute |
| 0.2 Text standard | PARTIAL | LIVE_API_PROVEN | `0b879ec4`, `dd576514` | 36068439450 | identity vs status-only | — | `test_response_composer.py` | Not ChatGPT-class certified |
| 0.3 Voice natural | PARTIAL | LIVE_VOICE_PROVEN (PCM) | `1f548ca8`, `0b2e42c3` | — | PCM convs | pcm JSON | spoken write + barge-in units | **HUMAN_EXPERIENCE_PENDING** |
| 0.4 Autonomous execute | PARTIAL | LIVE_API_PROVEN | WRITE + listing + CU READ | see §2 | plans completed | work_artifacts | lifecycle + listing + CU | Campaign factory DEFERRED; real CU WRITE BLOCKED_EXTERNAL |
| 0.5 READ/WRITE governed | PARTIAL | LIVE_API_PROVEN | `f7d13fba`, `dd576514`, `ecb86dcf` | see §2 | Observations + HubSpot ids | — | HMAC + listing + interact | Real CU WRITE BLOCKED_NO_AUTHORIZED_TARGET |
| 0.6 Artifacts | PARTIAL | LIVE_API_PROVEN | `f522a717`, `b6a9722c` | 36081750627, 36226281760 | conv `fb03f3fe` | `kind=table` / research_summary | `test_durable_work_session.py` | **LIVE_UI_PENDING**; campaign assets DEFERRED |
| 0.7 Visible execution | PARTIAL | CI_PROVEN / UX | `f8abdf14` / `dd41a3db` | — | CU `first_progress_ms` null | — | progress SSE tests exist | Progress SSE not LIVE on spoken CU; computer live-view LIVE_UI_PENDING |
| 0.8 Cross-modal continuity | PARTIAL | LIVE_API_PROVEN | same `conversation_id` HTTP+PCM | — | PCM + HTTP same org | GET `/state` | stream replay + cancel | Owner-live Plus **PENDING**; driving **HUMAN_EXPERIENCE_PENDING** |
| 0.9 Speed | PARTIAL | LIVE_API_PROVEN | see latency table | envelope tests | recorded ms | — | `test_section_0_latency_envelope.py` | Greeting not re-proven this pass; 10–30s is revoke |
| 0.10 Learning | PARTIAL | LIVE_API_PROVEN | proactive `4a1e84e9` | — | conv `5cfc0c14` | — | 3.0-J tests in tree | Store-row ≠ learned; H11 BUSINESS_IMPACT still human-labeled |
| 0.11 E2E journeys | NOT ACCEPTED | mixed | — | — | no twelve-point signed journey | — | — | **DEFERRED** until owner-live + mic + WRITE target |
| 0.12 One intelligence | COMPLETE for core | CI_PROVEN | current tree | 302 local | — | — | 2.0-A invariants | Hold: no second runtime |
| 0.13 Final question | NOT ACCEPTED | — | — | — | — | — | — | Blocked gates below |
| REQ-PX-001 cohesion | COMPLETE (core) | CI_PROVEN | current | 2.0-A | — | — | `test_platform_execution_2_0_a_invariants.py` | Plus UI owner-live PENDING |
| REQ-PX-009 strategy ≠ second brain | COMPLETE (core) | CI_PROVEN | CU uses ExecutionPlan | CU tests | — | — | CU + interact | — |
| REQ-PX-010 plan ≠ complete | COMPLETE on proven WRITEs | LIVE_API_PROVEN | `dd576514` | lifecycle | pending `executed` | — | `test_action_lifecycle.py` | — |
| REQ-PX-014 separate latency clocks | PARTIAL | LIVE_API_PROVEN | `runtime.turn_latency.critical_path` | — | CU server 2001 ms | — | turn_latency_trace | Progress SSE not a latency clock |

---

## Latency envelope (do not optimize)

| Path | SHA | First useful | Completion | Ceiling (revoke above) |
|---|---|---|---|---|
| Greeting Class A | `0b879ec4` | 4551 ms | 7638 ms | 8s / 12s |
| Governed provider READ | `c29f12cb` | 4114 ms | 6125 ms | 8s / 12s |
| Catalog search | `158c43eb` | 4803 ms | 7615 ms | 8s / 12s |
| CU first navigation | `bcff5702` | 4304 ms | 4760 ms | 8s / 12s |
| CU persisted follow-up | `bcff5702` | 1814–2666 ms | ≤3011 ms | 5s first useful |
| Artifact follow-up (listing table) | `f522a717` | 7115 ms | — | 12s |

---

## Observability

Traceable today without a new platform:

request → `conversation_id` → `execution_plan.plan_id` → ActionSpec or `execution_strategy=browser_cdp` → `pending_task` / HMAC → Observation (`execution_observations[]`) → `work_artifacts[]` → GET `/api/assistant/conversation/{id}/state` `execution_result` → follow-up resume flags `provider_reinvoked=false`.

Critical-path: `audit_events.action=runtime.turn_latency.critical_path`.

**Operator still infers:**

- Spoken CU `first_progress_ms` is null — progress SSE is not a live clock.
- Catalog live JSON on `158c43eb` has `execution_path=null` / `obs_count=0` even though later SHAs bind artifacts.
- Chromium process crash mid-session is not a dedicated LIVE recovery id.

Closed this pass: `map_stage("observation")` → `PROVIDER` (aligns `_mark("observation")` with the P2 contract).

---

## Interruption / recovery

| Scenario | Proven class | Note |
|---|---|---|
| Client disconnect / stop | CI_PROVEN | `test_chat_turn_cancel_service.py` |
| Stream replay / last-event skip | CI_PROVEN | `test_chat_stream_replay_service.py` |
| Reconnect after completed execution | LIVE_API_PROVEN | GET `/state` reconstruct; CU/listing follow-up |
| Reconnect after incomplete WRITE | CI_PROVEN | `recover_orphaned_executing` — **not LIVE crash-inject** |
| Duplicate yes / duplicate browser confirm | LIVE + CI | PCM duplicate; `test_duplicate_confirm_skips_second_invoke`; interact HMAC once |
| Browser process failure | NOT LIVE | Isolated context is CI source-locked; crash not injected |
| Navigation timeout | CI_PROVEN | empty link `count()==0` skip (was 8s hang) |
| Provider timeout / error | CI_PROVEN | HubSpot error classification |
| Artifact after process restart | LIVE_API_PROVEN | GET `/state` from DB task_state |
| Conversation reload | LIVE_API_PROVEN | same |

Do not claim Chromium crash-recovery LIVE.

---

## Security / governance (this pass)

Confirmed by existing tests, not redesigned:

- Tenant isolation and forbidden operator org.
- HMAC ActionSpec WRITE; interact confirm without HMAC does not submit.
- Frozen compile target; atomic claim `awaiting_confirm` → `executing`.
- No auto high-risk WRITE; spoken `yes wait` is hold.
- Duplicate protection.
- Browser `new_context(accept_downloads=False)` per READ; no authenticated browser reuse across tenants in this slice (public example.com).
- Interact WRITE not HubSpot.
- No secrets asserted in reconstruct tests (password column filtered in UI).
- No customer/prod mutation this pass.

---

## Final blocked gates (honest)

| Gate | Status |
|---|---|
| Physical mic | HUMAN_EXPERIENCE_PENDING |
| Owner-live Plus/UI | PENDING |
| Command OS signed-in presentation | not LIVE_UI_PROVEN |
| Real-world Computer Use WRITE | BLOCKED_NO_AUTHORIZED_TARGET |

After this package: **HOLD**, unless a new genuine regression appears or Cesar supplies owner-live session, physical mic, or an authorized isolated WRITE target.

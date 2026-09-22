# GRAVITRE — EVIDENCE CLOSURE (2026-09-22)

**Direction accepted:** PRESERVE + CONVERGE. **Not implemented.** No 3.0 / Computer Use build.

**Production identity (this closure):**
- Backend Railway `/health`: **`a7a0dd56`** @ `2026-09-22T06:31:33Z` · LIVE true · task tier **low**
- Frontend Vercel production: **`9eb88ee6`** `dpl_8HYCguvWjJ68SHcV6fePjUKv1pqA`
- Git `origin/main`: **`9eb88ee6`**
- `a7a0dd56` **is an ancestor** of `9eb88ee6` (frontend-only commits after backend tip). **Intentional independent deploys, compatible lineage.**

Isolated org only: `f07e57c0-1501-4000-8000-c04e57a00001`. Never operator org.

---

## WHAT IS PROVEN

1. HubSpot `deals.list` still LIVE on **current** backend `a7a0dd56`: conv `0d35dba2-…`, plan `1cbc5337-…`, “I found 25 deals”, `tool.invoke.completed` provider_invoked, Composer **canned**. First useful text **19931 ms**, complete **23199 ms**. **LIVE TEST VERIFIED**
2. Continuity follow-up “Only the large ones.” asks for cutoff, does not invent amount. Classical path. **LIVE TEST VERIFIED** (same SHA as #1)
3. Greetings use Composer **shortcut**, first text cold **6123 ms** / warm **2092 ms**. **LIVE TEST VERIFIED**
4. HTTP Talk (not mic): greeting first text **220 ms**, first audio **224 ms**, complete **1204 ms**. Tool-ish “Show my deals”: first audio **375 ms**, complete **18830 ms**. **LIVE TEST VERIFIED**
5. Isolated 24h fallthrough n=71: `defer_classical_tool_sse` 38, `pending_family_classical_resume` 19, `read_tool_classical` 14. **LIVE TEST VERIFIED**
6. Compiled CRM READ on this sample **did not emit** `unified_turn.live.fallthrough`; it went **straight classical** (`classical.answer_path.reached`). Sealed READ is **not** owned by LIVE. **LIVE TEST VERIFIED**
7. Ambiguous + WRITE clarify owned by **`unified_turn.live.completed`** (no provider invoke). **LIVE TEST VERIFIED**
8. CEO multi-source: LIVE **gpt-5.4-mini** / tier **low** / 8597 prompt tokens / **4736 cached (55%)** / visible_tools **20** / then **`read_tool_classical`** + ReAct (`searchKnowledgeBase`, workflow/agent/connector status). Did **not** call HubSpot/GA/Ads. **LIVE TEST VERIFIED**
9. 7d isolated outcome events sampled n=50: **only** `connector_action_executed`, `workflow_*`, `recommendation_created`. **Zero** `business_metric_improved`. **LIVE TEST VERIFIED**
10. PCM STT still works (`is Apollo connected.`) on `a7a0dd56`. Empty `assistant_text` **reproduced**. Interrupt events **2** (`speech.interrupted`, `bot-interrupted`) **before** transcript; 0 audio frames; `bot-llm-stopped`. **LIVE TEST VERIFIED**
11. HubSpot healthy + Google Ads healthy + Apollo healthy on isolated org **now**. GA/GSC/Gmail/QBO **pending_auth**. **LIVE TEST VERIFIED**

---

## WHAT REMAINS UNKNOWN

- Per-call cost dollars (no billing export).
- Physical microphone, barge-in with a human, WebRTC.
- Cross-surface resume (car → desktop → mobile approve) as one task id.
- Workflow child Observation identity vs chat (not traced this pass).
- Whether `outcome_bias_section` was non-empty on these turns (not in slim audits).
- Controlled mini vs 5.5 bake-off: **OPENAI_API_KEY absent locally** → benchmark **UNKNOWN**.
- Interruption/cancel/takeover milliseconds except PCM interrupt flags.
- Why Composer `clarify` recorded `success: false` while user-visible text was correct.
- Whether Google Ads healthy READ is compiled-sealed like HubSpot (not exercised).

---

## WHAT IS EXTERNALLY BLOCKED

- GA4 / GSC / Gmail / QuickBooks OAuth on isolated org (`pending_auth`).
- Human microphone / Lane B WebRTC (`production_allows_webrtc_media()==false`).
- Direct OpenAI tier bake-off from this workstation (no local API key).

---

## 1. Reconciled baseline vs 2.0 ledger

| Claim | 2.0 ledger / HubSpot artifacts | Master audit 2026 | This closure |
|-------|-------------------------------|-------------------|--------------|
| HubSpot READ | PASS on **older SHAs** (`c64e0352`, `6cd43ae3`, `4f98e744`, `b95a8735`) | Isolated HubSpot **BLOCKED / OAuth** | **Wrong for current org state.** HubSpot **healthy**; READ **PASS** on `a7a0dd56` |
| Continuity | PASS `4f98e744` / `6cd43ae3` | implied blocked | **Re-proven** same behavior on `a7a0dd56` |
| Voice PCM | 3.0 PCM STT PASS `c7d6b115`; empty assistant | empty spoken **UNKNOWN cause** | **Cause: false interrupt** on SAPI PCM; HTTP Talk **not** empty |
| LIVE vs ReAct as “48% broken dual brain” | 2.0 **wanted** compiled READ on classical/HMAC | Treat fallthrough as cohesion failure | Fallthrough is **mostly designed**: `read_tool_classical`, `defer_classical_tool_sse`, pending-family. **Do not collapse sealed READ into LIVE** |
| 2.0-K learning | UNIT: tool success ≠ business impact | WEAK consume | 7d sample **confirms**: no business-impact events; consume **cannot** fire |
| 2.0-L/M | scorecard + proactive unit | — | Not re-run; **UNIT/INTEGRATION still valid**; live notify still **NOT RUN** |
| SHA identity | mixed | “three SHAs must match” | **Incorrect requirement.** Need **release pair + lineage** |

Old HubSpot evidence remains valid **for those SHAs**. It does **not** certify a later SHA until re-run — **this closure re-ran**.

---

## 2. Production identity (corrected)

**Release pair (2026-09-22T06:31Z):**

| Surface | Provenance | Rollback |
|---------|------------|----------|
| API | Railway `git_sha=a7a0dd56` `/health` flags | Redeploy prior Railway image |
| Web | Vercel prod `9eb88ee6` `dpl_8HYCguvWjJ68SHcV6fePjUKv1pqA` (rollback candidate) | Vercel rollback to prior READY prod |
| Contract | Backend ancestor of frontend tip | Incompatible only if frontend requires APIs added **after** `a7a0dd56` without backend deploy — **none identified this pass (CODE: I3 TS cast / nav / connectors UX)** |

**Intentional:** frontend SHA ≠ backend SHA.  
**Accidental:** treating `/health` default-false LIVE as local truth (Settings vs prod).  
**Not a defect:** git HEAD tracking Vercel.

---

## 3. Latency waterfalls (current backend only)

Do not mix with 3.0-b SHA `7a2eaaab`.

| Class | Cohort | First useful text | Complete | Owner | Composer |
|-------|--------|-------------------|----------|-------|----------|
| Greeting | cold | 6123 | 9473 | shortcut | shortcut |
| Greeting | warm same conv | 2092 | 5081 | shortcut | shortcut |
| General | cold | 2632 | 5586 | shortcut | shortcut |
| HubSpot READ | cold | **19931** | 23199 | **classical HMAC** | canned |
| HubSpot follow-up | warm | 16787 | 19495 | classical + KB search | clarify (success false) |
| Ambiguous | cold | 16574 | 20790 | **LIVE completed** | success |
| WRITE clarify | cold | 15756 | 18750 | **LIVE completed** | success |
| Multi-source | cold | **31140** | 33703 | LIVE then classical ReAct | success |
| Voice HTTP greeting | — | 220 | 1204 | HTTP Talk | audio 224 |
| Voice HTTP deals | — | 324 | 18830 | HTTP Talk | audio 375 |

**Ranked on this SHA:** (1) CEO/multi-source LIVE+ReAct 31s (2) HubSpot compiled READ 20s TTFT (3) LIVE conversational 16s (4) greeting shortcut 2–6s (5) HTTP Talk greeting <1.3s.

Composer **shortcut/canned** is **not** the HubSpot 20s tax. Prior 18s Composer p50 was a **different cohort**.

---

## 4. Model / prompt inventory (from live fallthrough meta)

Only the CEO turn dumped a full LIVE breakdown:

- Selected: **gpt-5.4-mini** · provider openai · `task_model_tier=low` **governs that LIVE attempt**
- Does **not** govern HubSpot compiled READ (no LIVE model call in that audit window)
- prompt_tokens 8597 · completion 47 · cached 4736 · ratio 0.5509
- system_prompt_chars 22362 · messages_chars 35565 · tools_payload_bytes 4691 · visible 20 / catalog 86
- model_ttft_ms 1326 · model_total 1390 · auto_schema_retry_ms **1742** · then fallthrough
- Cost: **UNKNOWN**

Greetings: no model row (shortcut).

---

## 5. Model benchmark

`scripts/audit-model-tier-benchmark.py` → **UNKNOWN** (`OPENAI_API_KEY` not in local `.env`). Do not invent mini vs 5.5 quality. **Recommendation stands as eval**, not a selection.

---

## 6. LIVE / ReAct ownership (canonical without one loop)

| Class | Owner on `a7a0dd56` | Why |
|-------|---------------------|-----|
| Compiled deterministic HubSpot READ | **Classical + HMAC** | Sealed 2.0 contract; no LIVE fallthrough event |
| Follow-up refine/clarify | Classical (+ optional KB) | Continuity |
| Ambiguous / WRITE missing slots | **Unified LIVE completed** | No tool |
| Multi-step exploratory | LIVE attempt → `read_tool_classical` → **ReAct** | Duplicate model work |
| PendingAction family | `pending_family_classical_resume` | Designed fallthrough |
| Workflow child | **UNKNOWN this pass** | |

**Canonical contract:** one **Observation + ExecutionPlan + HMAC**, two **strategies** (compiled sealed READ vs model tool loop). Fallthrough is a **router**, not a second product — **except** exploratory READ paying LIVE then ReAct.

24h isolated: 71 fallthrough vs 72 classical.reached vs 35 invoke.completed vs 165 composer.

---

## 7. Memory / KF / learning

Trace attempted: HubSpot READ Observation (25 deals) → later “large ones” **did not** re-query deals; asked cutoff. Memory **recalled**. KF `searchKnowledgeBase` on follow-up **did not** change the cutoff question (redundant).

CEO question: KF + internal status tools **substituted** for HubSpot/Ads/GA. KF **did not improve** connector execution; it **competed**.

Learning: 50 events all **TOOL_SUCCESS** class. `outcome_bias` cannot be business-driven. 2.0-K honesty holds. **Closed loop of measured business outcome → later plan: NOT PROVEN.**

Mechanisms: LLM (LIVE/ReAct), embeddings (JIT + KB), rules (HMAC, shortcut, cutoff clarify), heuristics (fallthrough enum). **No trained weights serving this kernel.**

---

## 8. Voice

| Path | Result |
|------|--------|
| HTTP Talk | First audio 224–375 ms; deals complete 18.8s |
| PCM SAPI | STT OK; **empty spoken**; interrupts before transcript |
| Human mic | EXTERNALLY BLOCKED |

**Empty spoken cause:** false barge-in (`speech.interrupted` / `bot-interrupted`) on synthesized PCM, LLM stop with no `assistant_text` / PCM out. **Not** “Composer always empty.” HTTP Talk proves spoken deltas exist.

Parity: same org, “Show my deals.” text = 25 deals canned; HTTP Talk complete 18.8s (text of audio **not captured** this pass — first audio exists). PCM phrase ≠ text greeting.

---

## 9. Computer execution (eval only)

**Reuse:** ExecutionPlan, task_state, ActionSpec/HMAC, PendingAction, Observations, durable_checkpoint, Composer, AI Workspace SSE.

**Existing foundation:** `browser_agent_service` httpx READ + Playwright interact **flag default false**, approval_id required, SSRF blocks. Headless, **no** live view.

**Provider category (not a vendor lock-in pick):** hosted **CDP browser** with live view + session recording (Browserbase / Steel / Kernel class) **or** visual computer-use API on a headful VM. Orchestration **must stay** Gravitre kernel. Browser actions = ActionSpec strategy `browser.act` / `computer.act` with PendingAction for writes, Observations = screenshot hash + DOM summary + CDP log — never a second brain.

**Must have:** visual stream into workspace, pause=checkpoint, takeover=human CDP, tenant-isolated sessions, credentials via existing connector vault **not** in the model, HMAC-equivalent authorization, bounded recovery.

---

## 10. Machine-readable files

See `docs/audits/gravitre-evidence-closure-live.json`, `gravitre-pcm-closure-live.json`, `gravitre-contradiction-reconciliation.json`, `gravitre-release-pair.json`, `gravitre-execution-strategy-trace.json`, `gravitre-learning-consumption-trace.json`, `gravitre-voice-parity-trace.json`.

---

## Explicit close

**PRESERVE:** HMAC sealed READ, shortcut Composer, HTTP Talk SLO path, JIT 20 tools, release-pair model, pending_auth, STA-312.  
**CONVERGE:** Observation schema; exploratory LIVE→ReAct double pay; KF vs connector retrieval.  
**OPTIMIZE FIRST:** compiled READ TTFT (~20s); exploratory fallthrough duplicate model; PCM false interrupt.  
**NEW STRATEGY later:** hosted browser/computer under ExecutionPlan.  
**DO NOT BUILD:** second brain, 3.0 rewrite, collapsing sealed READ into LIVE, Computer Use this sprint.

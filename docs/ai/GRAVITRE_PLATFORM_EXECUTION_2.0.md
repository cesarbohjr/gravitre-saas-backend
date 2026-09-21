# Gravitre Platform-Wide Execution 2.0

**Status:** IMPLEMENTATION COMPLETE — EXTERNAL PROOF PENDING (not 2.0 PROGRAM COMPLETE)  
**Date:** 2026-09-21  
**Grounding:** this spec + `docs/delivery/gravitre-2.0-requirement-ledger.json` + live HubSpot READ on Railway `b95a8735`  
**Product behavior (not a Manus clone):** objective → understand → context → how → right systems → execute safely → recover → synthesize → explain → learn.

Cesar authorized full 2.0 implementation on main. Remaining LIVE_PROVEN gaps are recorded as EXTERNAL_BLOCKED (GA4/GSC OAuth, authenticated browser SSO, voice first audible PCM). Do not treat those as failures of unimplemented code.

No customer-facing prices, Certified/TRAINED badges, or Enable toggles. Certification remains [internal Track A/B/C scorecard](../delivery/connector-certification-states.md) (`connector_certification_scorecard.py`).

### A0 corrections (do not treat the original diagram as executable order)

1. **E5 before E4 is plan-shell only (A, not B).** `reconcile_execution_plan` is deterministic continuity (pending/offered/pending_task/recipe shell). It is **not** foundation-model execution planning. Keep it early for lineage; do not reorder solely to match a prettier diagram.
2. **Kernel `CognitivePlanner` PLAN** (inside `run_pre_act`) is heuristic `plan_kind=strategic_reasoning`, `executable=False` — also **not** FM execution planning. It is **not** the ExecutionPlan SoT.
3. **ContextCompiler-before-model:** LIVE compiles `compile_unified_reasoning_context` then `apply_unified_turn_live`. Classical compiles `compile_assistant_turn_context` then ReAct/`tool_choice`. Analytics SC **disables LIVE** and runs **after** classical E4.
4. **`compiled_task` is OPTIONAL_PROJECTION, not a gate and not SoT.** Do not expand `compiled_task_service` as a second runtime. Mutating the blob must never change execution truth (already reprojected on persist).
5. **Voice is not globally ALREADY_COMPLETE.** Shared kernel = STRUCTURAL_COMPLETE; live semantic parity / latency / barge-in = NOT_RUN or UNKNOWN this pass.
6. **SC is still a second analytics compiler**, not merely FAST_PATH: own intent detect, time fallback, resource resolve, companion `run_ga4_report` (no HMAC), overview copy (“last 30 days”). Primary `analytics.reports.run` is HMAC + `invoke_tool`.

---

## Classification key

| Label | Meaning |
|-------|---------|
| **ALREADY_COMPLETE** | Current architecture already provides the behavior (may still need live proof) |
| **EXTEND_EXISTING** | Grow F1/E1–E5/F2 without a new core |
| **CONVERGE** | Multiple paths exist; fold into one owner |
| **DEPRECATE** | Stop treating as SoT (keep adapter until cutover) |
| **NEW_REQUIRED** | Missing layer; add only if existing types cannot represent it |

---

## 1. Re-audit findings this spec addresses

| Finding | 2.0 response | Class |
|---------|--------------|-------|
| Compiler island vs ReAct majority | Compile-before-`tool_choice` for operational READs; ReAct under harness | CONVERGE |
| F1 = five HMAC keys only | Expand READ fabric by priority, same contract | EXTEND_EXISTING |
| Traffic SC companion `run_ga4_report` BYPASSED HMAC | Same proof or drop companion until sealed | CONVERGE |
| “Last 30 days” copy after calendar compile | Composer/handler must use compiled window | EXTEND_EXISTING |
| `compiled_task` projection not ingress authority | Keep as **OPTIONAL_PROJECTION** of E1+E5+F1/preflight; **not a gate**; **no second BusinessTask runtime** | CONVERGE (projection only) |
| Fresh single-connector still ReAct-first | Preflight/compile on operational intents, not only orchestration | CONVERGE |
| LIVE disabled on analytics SC | Keep until generic compile matches SC; then fold SC into gate | CONVERGE then DEPRECATE SC as core |
| ~75 vendors `resolver_not_implemented` | Adapter registry, not cognitive branches | EXTEND_EXISTING |
| 13 capabilities / 22 bound actions | Recipes for department intents, not 732 IDs | EXTEND_EXISTING |
| No CRM=billing=Zendesk join | Entity fabric with evidence/confidence | NEW_REQUIRED |
| No causal multi-source compiler | Hypothesis/evidence loop on ExecutionPlan | NEW_REQUIRED (uses E5) |
| F2 one-shot | Bounded repair budget by class | EXTEND_EXISTING |
| Writes ungated by F1 | Keep governance; later same compile **without auto-authorize** | EXTEND_EXISTING (later) |
| No financial write class | Add risk class on ActionSpec / authority | EXTEND_EXISTING |
| ReAct `plan_runtime` optional | Require plan lineage for connector invoke | CONVERGE |
| SSE `Stopped.` bypass | Composer-only | CONVERGE |
| MCP/SDK/catalog_http bypass | Same harness or explicit not-production | CONVERGE |
| Voice unmeasured | Same kernel STRUCTURAL; do not label live/parity/latency complete | EXTEND_EXISTING |
| CI red / live F1 NOT RUN | Proof gates before expansion | ALREADY_COMPLETE architecture; **ops** |
| Certification mixed CONNECTED vs ready | Keep process doc; no customer badge | ALREADY_COMPLETE process |

---

## 2. Target architecture (one harness)

**Corrected canonical order (target + current truthful split):**

```
DETERMINISTIC TURN/TASK RESOLUTION
  Ingress (`/ai`, `/agents/[id]/chat`, voice `spoken_mode`)
  → Intent Gateway (chitchat/FAQ only; not operational SoT)
  → E1 resolution + capability route + time
  → E5 ExecutionPlan reconcile (deterministic shell / continuity only)
  → CognitiveTurnKernel run_pre_act (RETRIEVE/RECALL/KNOWLEDGE + heuristic PLAN; not FM exec plan)
        ↓
ContextCompiler (CompiledTurnContext / unified reasoning compile)
        ↓
MODEL REASONING / PLANNING IF NEEDED (LIVE or ReAct) — never without compiled context
        ↓
ExecutionPlan step compilation (ActionSpec + resource + params) when the strategy executes
        ↓
HMAC Preflight (F1 keys) → invoke_tool / adapter → Observation → Composer → trace
```

**Allowed earlier:** deterministic plan **identity/shell** (E5) for lineage.  
**Forbidden:** model-generated execution planning or ReAct `tool_choice` as the owner of resources/params **before** CompiledTurnContext.

**Current runtime (A0, not yet cohesive):**

| Path | Sequence |
|------|----------|
| Simple conversational | Gateway and/or LIVE after unified compile; no provider |
| Simple READ (F1 key, not traffic SC) | E1 → E5 shell → kernel → E4 → ReAct `tool_choice=auto` (narrowed catalog, not compiled-eligible-only) → F1 preflight on invoke |
| ReAct READ | Same; ReAct still chooses raw provider tool from narrowed set |
| Multi-step analysis | E5 may attach heuristic cross-source shell; LIVE off if SC flag; else ReAct/LIVE after compile |
| WRITE requiring approval | E5 continues pending/offered plan; `react_write_gate` / PendingAction; **no F1 HMAC compile**; same-plan continuation on confirm |
| Voice READ | Same `execute_task_streaming(spoken_mode=True)` after STT; LIVE may be on unless SC; progress via Composer `kind=progress` |
| Traffic “last month” | E1 SC flag → LIVE **disabled** → classical E4 → analytics SC (HMAC primary + **companion HMAC bypass**) → Composer wrap |

**Provider adapters allowed. Competing cognitive cores not allowed.**

---

## 3. Existing architecture preserved

- F1 ActionSpec Option B + HMAC `preflight_result` + stale detection  
- `canonical_time_resolver` + documented no-phrase `30daysAgo` default  
- Tenant-scoped `domain_property_binding` (no cross-org)  
- Write approval, `react_write_gate`, canvas write authority, G8  
- Response Composer as prose SoT  
- STA-303 `auth_expired` vs `tool_not_available`  
- Optional GSC on traffic recipe (not second exclusive vendor on `analytics.traffic_overview`)  
- `CAN_THIS_ACTION_EXECUTE_NOW` cheap attach (no per-tool `force_live`)  
- Dual `/ai` workspace reuse (not a third chat runtime)  
- Voice = `execute_task_streaming(spoken_mode=True)`  
- Memory Phase 1 exact HMAC mentions (not fuzzy `"Sarah"`↔`"Sarah Smith"`)  
- Certification **process** Track A/B/C — no customer Certified chip  

---

## 4. Components extended

| Component | How |
|-----------|-----|
| `ActionSpec` / `f1_read_slice` materialize | More READ keys, then governed WRITEs |
| `read_preflight` / `enforce_invoke_preflight` | Same contract, wider `is_*_read_action` or spec flag |
| `canonical_time_resolver` | More phrases; all consumers use compiled window in copy |
| `connector_resource_adapters` | High-value vendors; GA4 stays adapter not core |
| `capability_ontology` + recipes | Department intents |
| `compiled_task_service` | **OPTIONAL_PROJECTION** only; do not grow as gate/SoT |
| `execution_plan_service` | Required lineage on connector invoke |
| `f2_read_repair` | Classed budget |
| `action_execute_now` | Optional per-action snapshot without live probe spam |
| `catalog_write_authority` | Financial / external / HR / security classes |
| ContextCompiler | Inclusion trace; less duplicate RAG |
| Golden traffic + department goldens | Permanent regressions |

---

## 5. Components deprecated (as SoT — adapters until cutover)

| Component | Deprecation |
|-----------|-------------|
| Analytics short-circuit as **parallel compiler** | After generic compile equals SC quality; keep as **fast path that calls the same preflight** |
| ReAct owning params/resources | ReAct proposes; harness compiles |
| `action_parameters.py` as SoT | Projection from ActionSpec |
| Intent Gateway operational answers | Chitchat/FAQ only |
| IH deterministic as second brain | Same harness or explicit canned non-execution |
| Direct `run_ga4_report` without proof | CONVERGE companions |
| `sse_text_delta` user prose | Composer only |
| Health-matrix `resource_aware` as SoT | Align with adapter registry + `resource_requirements` |
| Customer “connected = all actions” copy | Track B vs Track A language internally |

---

## 6. New components only where necessary

| Proposed | Why not existing? |
|----------|-------------------|
| **BusinessEntity** + **provider bindings** (evidence, confidence, no silent merge) | KG/resolution records exist but **no join** CRM=QBO=Zendesk |
| **CapabilityRecipe** declarative (sources, min/optional, synthesis) | Traffic recipe exists ad hoc; not general |
| **Hypothesis/evidence plan steps** | E5 can hold them; may need step kinds, not a new planner product |
| **RepairBudget** policy table | F2 is one-shot hardcoded |
| **Financial/risk class** on ActionSpec | Authority has no financial taxonomy |

**Do not add:** second BusinessTask runtime, second voice brain, customer certification UI, parallel connector subsystem.

---

## 7. Business identity model

**EXTEND_EXISTING** `merge_business_identity` / org settings / KG / branding domain.

Canonical **tenant-scoped** facts: company name, primary website/hosts, brands, locations. Bind to connector resources via resolver (already: unique host → GA4/GSC). **Do not** make `property_id` the identity.

`BUSINESS_IDENTITY` as a ParameterSourceRule may **select** a unique bound resource; it must not invent IDs.

---

## 8. Entity resolution model

**NEW_REQUIRED** join layer on top of `org_entity_resolution_records` + Memory HMAC.

`BusinessEntity { id, org_id, display_name, kind, bindings[{system, resource_type, resource_id}], evidence[], confidence }`

Rules: never silent merge below threshold; Memory remains exact HMAC; fuzzy person names stay rule-based store (engineering standards). PII / third-party ML still needs named owner (STA-312 class) — schema-gate ≠ authorization.

---

## 9. Capability architecture

**EXTEND_EXISTING** 13 IDs. Target **business intents**, not 732 APIs.

Examples (add only with recipes): `analytics.website_performance`, `sales.pipeline.health`, `finance.receivables.overdue`, `support.issue_trends`, `calendar.meeting.schedule`, `communication.email.send` (alias of `email.send`), `executive.attention`.

A capability maps to one action, substitutes, parallel reads, workflow, or delegation — **not** one ID per catalog row.

---

## 10. Source-selection architecture

**EXTEND_EXISTING** execute-now + connected list + recipes.

Order for operational asks: live systems → org graph → company knowledge → memory → expert → web → model. Golden E already UNIT_TEST for traffic-without-connector. Generalize `should_suppress_knowledge_base_for_turn`.

---

## 11. Resource architecture

**EXTEND_EXISTING** `ResourceResolution` + adapters.

Standard `ResourceDefinition` fields as **adapter output**, not 77 cognitive branches. Align health-matrix zendesk omission. High-value adapters first (CRM, billing, support, calendar, mail, analytics).

---

## 12. ActionSpec architecture

**EXTEND_EXISTING** Option B. Production actions eventually own: schema, source rules, resources, scopes, capabilities, constraints, governance, adapter, observation, availability, `spec_revision`.

Other schemas = **PROJECTION** or **VALID_PROVIDER_GUARD**.

---

## 13. Parameter compilation

**EXTEND_EXISTING** F1 provenance chain.

Priority (high→low): explicit user → structured reference/task → identity/entity → ResourceResolver → connector metadata → time resolver → recipe → observations → safe defaults → model → clarify.

Lower authority cannot overwrite deterministic facts (golden F).

READs first; WRITEs later **without auto-authorization**.

---

## 14. READ architecture

HMAC + plan/step + Observation for **priority** READs, not all 732.

Priority: F1 five (seal companions) → HubSpot contacts/companies/tickets reads → Gmail/Slack/calendar reads → Salesforce → Stripe list. Usage/customer value over alphabet.

---

## 15. WRITE architecture

**EXTEND_EXISTING** after READ live-proof.

Same compile → policy/risk → **approval** → ExecutionPlan step → execute → verify → observe.

Derive known facts; **never** auto-approve financial/destructive/external/HR/security.

---

## 16. Preflight

**EXTEND_EXISTING** F1 HMAC. No provider call without valid action, tenant, resource, params, availability, schema, constraints, permission, governance. Proof internal, bound, not `_preflight_ok` in params.

---

## 17. Self-repair

**EXTEND_EXISTING** F2.

Class table from re-audit + master prompt. Budget: transport 2, argument repair 1–2, resource rediscover 1, sibling 1, source switch 1, replan 1. Trace every recovery. No infinite loops. No retry of same malformed args (HubSpot search/list lesson).

---

## 18. ExecutionPlan

**CONVERGE** optional `plan_runtime`. Connector `invoke_tool` requires plan_id/step_id (synthetic single-step plan allowed for trivial READs). Gateway/IH that skip execution stay out; if they execute, they must attach a plan.

---

## 19. ReAct

**CONVERGE** — strategy only. Does not own context, task, resources, ActionSpec, param truth, governance, completion. Propose tools from **narrowed compiled-eligible** set.

---

## 20. Workflows

**EXTEND_EXISTING** — execution strategy. Conversation: invoke → observe → continue on same plan. Canvas write authority preserved.

---

## 21. Delegation

**EXTEND_EXISTING** — roles over **one** core. Child gets scoped CompiledTurnContext, parent plan/step, permissions; returns observations, not a new brain.

---

## 22. Text experience

**CONVERGE** Composer. Derive-before-ask. Business language. No tool keys in user prose. Close `Stopped.` leak.

---

## 23–27. Voice (A0 reclassified — not globally complete)

| Aspect | Class | Evidence |
|--------|-------|----------|
| Architectural sharing (same `execute_task_streaming`) | **STRUCTURAL_COMPLETE** | `voice_session_service` / Pipecat → `spoken_mode=True`; `voice_plan_equivalence` |
| Behavioral / semantic parity (capability, entity, time, plan, resource, action) | **UNKNOWN** | No text/voice ID pair this pass |
| Live execution | **NOT_RUN** | No A0 spoken probe; prior voice docs are older SHAs |
| Latency (speech_end → first audible PCM) | **UNKNOWN** | Not instrumented on `f4accdfc` this pass |
| Barge-in safety vs WRITE | **PARTIAL** | Interrupt/stop paths exist; WRITE-target live proof **NOT_RUN** |

Do not label voice **ALREADY_COMPLETE** until semantic parity and live execution have evidence.

---

## 28. ContextCompiler

**EXTEND_EXISTING** — quality not volume. Trace INCLUDE/EXCLUDE. Avoid RAG+compiled_task+org_context duplication.

---

## 29. Memory

**EXTEND_EXISTING** — keep buckets separate: conversation, working task, org facts, entity bindings, decisions, outcomes, preferences. Exact HMAC unchanged.

---

## 30. Outcome learning

**NEW_REQUIRED** closed loop: objective → plan → action → observation → **business impact** → memory. Not “tool succeeded.” Defer until READ observations are trustworthy.

---

## 31. Proactive

**DEFER** (2.0-M) until reactive quality. Signals → notice / READ investigation / recommend; **no** high-risk auto-WRITE. No invented alert SKUs.

---

## 32. Connector certification

**ALREADY_COMPLETE** as process. **EXTEND_EXISTING** internal scorecard from existing signals. **Do not** ship customer Certified/TRAINED/live badges. CONNECTED ≠ all actions (Track B vs A).

---

## 33. MCP / SDK / catalog_http

**CONVERGE** — ActionSpec + capability + resource + provenance + preflight + governance + tests, or labeled **not production-autonomous**.

---

## 34. Knowledge Fabric

**EXTEND_EXISTING** hierarchy: policy/RAG vs live operational. Do not let web/RAG win operational asks.

---

## 35. Intelligence

**CONVERGE** — same entities/plans/evidence. No second truth model. IH deterministic shortcuts that skip compile are **DEPRECATE** for execution.

---

## 36. Response Composer

**ALREADY_COMPLETE** mandate. **CONVERGE** remaining SSE. Modalities: TEXT / VOICE / PROGRESS / CLARIFICATION / APPROVAL / PARTIAL / ERROR / SUCCESS. Approval copy in business language (“Send this email to Sarah Khan?”).

---

## 37. Tracing

**EXTEND_EXISTING** E2. Stable IDs: turn, conversation, task, plan, step, pending, capability, action, resource, observation, outcome. Reconstructability required for LIVE_PROVEN.

---

## 38. Latency architecture

Measure first (re-audit UNKNOWN). Then: parallel independent READs, cache ActionSpec/resources, prefetch context, stream TTS, deterministic classifiers. **No speculative WRITEs.** Report budget per phase.

---

## 39. Security / governance

Preserve write gates, tenant isolation, HIPAA tool invoke, interrupt-near-WRITE. Financial class addition is **labeling**, not auto-exec. Entity joins: PII owner required.

---

## 40. Test / eval architecture

Keep golden A–G. Add department goldens, text/voice parity, repair, approval, tenant isolation. Live isolated-org smoke **required** for LIVE_PROVEN. CI standing-red: document owners or fix **before** claiming 2.0-A complete.

---

## Diagrams

### A. Canonical turn pipeline

```
User (text|voice)
  → Ingress (shared workspace / Pipecat)
  → Gateway? (non-operational only)
  → E1 resolve + capability + time
  → E5 ExecutionPlan **shell** (lineage; not FM planning)
  → kernel pre-act (retrieve; heuristic PLAN ≠ exec SoT)
  → E4 ContextCompiler  **required before FM / ReAct**
  → strategy (fast path | ReAct | workflow | LIVE) under compiled context
  → compile resources+params+availability + HMAC (F1)
  → invoke_tool / adapter (plan_id/step_id required for cognitive connector invoke — **not yet enforced globally**)
  → observe / repair budget
  → Composer → text and/or TTS
  → trace LEARN
  compiled_task = optional derived view (never a dispatcher SoT)
```

### B. Text path

Same A; SSE from Composer; `/ai` and `/agents/[id]/chat` share workspace.

### C. Voice path

VAD/STT/endpointing → **same A** (`spoken_mode`) → Composer voice rendering → TTS. Barge-in → interrupt → pending/WRITE safety.

### D. READ lifecycle

Capability/recipe → ActionSpec → resource → params → execute-now → HMAC → provider → Observation → compile into plan.

### E. WRITE lifecycle

Same compile → risk class → PendingAction / approval (business language) → execute → verify → Observation. No auto-authorize.

### F. Self-repair

Failure class → budget remaining? → repair | sibling | source switch | retry | replan | clarify | fail → trace.

### G. Multi-source reasoning

Question → hypotheses (plan steps) → required evidence from recipe → parallel safe READs → update hypotheses → conclude or insufficient.

### H. Agent delegation

Parent plan step → child role + scoped context → child observations → parent synthesize.

### I. Connector onboarding

Catalog ActionSpec + adapter + capability map + tests + Track A scorecard. **No cognitive-core edit.**

### J. Entity / resource

```
BusinessEntity (org-scoped)
  bindings → HubSpot company | QBO customer | Zendesk org
Website identity → GA4 property | GSC site | ads account
Employee → email | calendar | Slack
```

---

## Phased migration (reconciled with re-audit, not master-prompt order blindly)

Live proof and safety **before** autonomy expansion.

| Phase | Objective | Why now | Deps | Owners | Files (indicative) | Protected | Tests | Live | Latency | Risks | Gate |
|-------|-----------|---------|------|--------|--------------------|-----------|-------|------|---------|-------|------|
| **2.0-A0 Proof** | Isolated-org F1/SC live smoke; SHA match; golden artifact; CI honesty | Re-audit NOT RUN / CI red | Secrets, Railway | Runtime | `smoke-golden-benchmark-live.py` | F1 slice | existing goldens | **Required** | baseline capture | EXTERNAL_BLOCKED | Artifact + `/health` SHA |
| **2.0-A Cohesion** | Invariant I: operational compile before strategy; seal SC companions; Composer-only SSE; plan lineage on invoke; fix 30d copy | Competing cores | A0 | Runtime | `agent_intelligence`, `analytics_traffic_overview_service`, `assistant.py`, `react_engine` | WRITE/G8, F1 HMAC | goldens A–G + companion HMAC test | prod traffic turn | no extra LLM | SC fold too early | UNIT_TEST + one LIVE_PROVEN traffic |
| **2.0-B Identity/entity** | Extend identity bind; **new** join store with confidence | CS-6/13 | A | Catalog/runtime | `domain_property_binding`, entity store | Memory HMAC exactness | bind + no silent merge | multi-property org | resolver cache | PII | Unique bind LIVE_PROVEN |
| **2.0-C Recipes + sources** | Declarative recipes; retrieval hierarchy | Thin ontology | A | Ontology | `capability_ontology`, replanner | GSC optional-not-exclusive | recipe tests | dual GA4+GSC | parallel READ ok | recipe explosion | 3 recipes live |
| **2.0-D READ fabric** | Next N high-value READs on F1 contract | 725 unprotected | A–C | Catalog | ActionSpec, preflight flag | WRITE | per-action goldens | isolated org | preflight ms budget | ReAct behavior change | N keys HMAC in prod |
| **2.0-E Repair budget** | Classed F2 | Post-provider WEAK | D | Runtime | `f2_read_repair` | no invalid invoke | repair tests | one sibling live | bounded | loops | budget traces |
| **2.0-F WRITE compile** | Same semantics, **approval stays** | Inconsistent READ/WRITE compile | D live-proof | Governance | ledger + ActionSpec | auto-WRITE | approval UX tests | governed send | n/a | unsafe auto | no WRITE without approval |
| **2.0-G Multi-source** | Pipeline/AR/support diagnostic | WEAK reasoning | C–E | Runtime | plan step kinds | don’t fake evidence | “why pipeline” golden | connected CRM+analytics | parallel | overclaim | insufficient-evidence honesty |
| **2.0-H Continuity** | One task frame; references | CS-7 | A, E5 | Runtime | conversation_state | pending family | multi-turn tests | live A–D | n/a | restart intent | follow-up updates compiled_task |
| **2.0-I Voice parity** | STT+context; same semantics | UNKNOWN voice | A same kernel | Voice | pipecat, composer voice | WRITE targets | parity suite | spoken A/F | SLO TBD after baseline | wrong WRITE target | text/voice equivalent IDs |
| **2.0-J Voice latency/barge-in** | Instrument + barge-in WRITE safety | UNKNOWN p95 | I | Voice | TTS, interrupt | speculative WRITEs | latency CI | prod voice | p50/p95 published | hiding stages | SLO not worse |
| **2.0-K Memory/outcomes** | Outcome ≠ tool ok | WEAK learning | G observations | Memory | LEARN path | opt-in PII | unit | opt-in org | n/a | stale memory | documented loop |
| **2.0-L Certification/long-tail** | Internal Track A scorecard; MCP harness | process vs generated | D | Catalog | scorecard from existing JSON | customer badges | matrix regen | n/a | n/a | fake Certified UI | internal only |
| **2.0-M Proactive** | Attention synthesis | After reactive | G, K | Product | signals → Composer notice | auto-WRITE | quiet tests | opt-in | n/a | noise | no high-risk auto-exec |

**Rollback:** feature flags per phase; HMAC remain on existing F1 keys; SC fast path stays until A gate green.

---

## Work-item map (master prompt §0–71)

| Item | Class |
|------|--------|
| One harness / compilers / ActionSpec / capability / resource / param / preflight / observation / Composer / text=voice semantics | CONVERGE (partially true) |
| Business task fields | CONVERGE via `compiled_task` projection — **not** NEW runtime |
| Derive before ask | EXTEND_EXISTING E3 |
| Identity fabric | EXTEND_EXISTING |
| Cross-system entity | NEW_REQUIRED |
| Ontology 2.0 / recipes / source selection | EXTEND_EXISTING |
| ResourceDefinition / adapters | EXTEND_EXISTING |
| ActionSpec 2.0 / param 2.0 | EXTEND_EXISTING |
| READ fabric | EXTEND_EXISTING |
| WRITE fabric + confirmation language | EXTEND_EXISTING (later) |
| Reversibility classes | EXTEND_EXISTING |
| Universal preflight | EXTEND_EXISTING |
| Self-repair + budget + wrong-action | EXTEND_EXISTING |
| Active task / references | CONVERGE |
| Reasoning / multi-source / evidence | NEW_REQUIRED on E5 |
| Planning quality | EXTEND_EXISTING |
| ReAct under harness | CONVERGE |
| Workflow / delegation | EXTEND_EXISTING |
| Text 2.0 | CONVERGE Composer |
| Voice 2.0–latency | EXTEND_EXISTING (kernel STRUCTURAL_COMPLETE only) |
| Fast paths | CONVERGE (SC becomes fast path over same preflight) |
| Model routing | EXTEND_EXISTING after measure |
| ContextCompiler 2.0 | EXTEND_EXISTING |
| Memory / learning / proactive | EXTEND / NEW / DEFER |
| Commonsense contract | EXTEND golden suite |
| Connector contract / cert / priority / MCP | EXTEND process + CONVERGE generated |
| KF / Intelligence | CONVERGE |
| Observability / explainability | EXTEND_EXISTING |
| Error UX / honesty | EXTEND_EXISTING |
| Benchmarks / parity / latency | EXTEND_EXISTING |
| No special-case accumulation | CONVERGE SC/GA4 companions |
| Quality before autonomy | **POLICY** — binding |

---

## Completion criteria (program)

2.0 is **not** “all 732 HMAC’d.” It is:

1. Operational turns share **one compile+preflight contract** (SC is a fast path, not a second compiler).  
2. Priority READ connectors customer-valuable are HMAC + live-proven.  
3. WRITEs compiled **and** still approved.  
4. Text and voice share IDs; voice SLOs measured.  
5. Commonsense goldens A–G plus department set.  
6. No customer certification chrome.  
7. “If the user omits connector names, ordinary work still compiles” — **YES** for certified recipes, honest fail otherwise.

---

## Production verification / rollback

- Evidence: `/health` SHA, `audit_events`, conversation_id, golden live JSON.  
- UNIT_TEST ≠ LIVE_USER_PROVEN.  
- Rollback: flags; never remove F1 enforce on existing keys.

---

## A0 evidence appendix (2026-09-18)

### compiled_task field owners (OPTIONAL_PROJECTION)

| Proposed field | Canonical owner today |
|----------------|------------------------|
| objective | E5 `ExecutionPlan.objective` / resolution message |
| business objects / entities | identity merge + `ResourceResolution` + KG (join still NEW_REQUIRED) |
| timeframe | `canonical_time_resolver` / `PreflightResult.time_window` |
| capability | `capability_router` / plan `capability_id` |
| sources / resources | `resolve_resource` + plan steps |
| action keys | plan steps / ActionSpec id |
| compiled params | `PreflightResult.compiled_parameters` / ActionSpec |
| clarification | E3 / resource ambiguous decision |
| preflight state | `PreflightResult` |

Problem a projection *can* solve: one **read-only** compiler/trace slice. Problem it **cannot** uniquely solve that E4+plan+preflight lack: execution gating. **Decision: OPTIONAL_PROJECTION — do not expand as SoT.**

### SC companion HMAC inventory (do not fix in A0)

| Caller | ActionSpec | plan/step | resource | param compiler | HMAC | invoke_tool | Observation | Composer |
|--------|------------|-----------|----------|----------------|------|-------------|-------------|----------|
| Traffic SC primary | `google_analytics.reports.run` / `analytics.reports.run` | via preflight if plan in state | `resolve_resource` | F1 `preflight_read_action` | **yes** | **yes** | implicit tool result | handler copy then Composer wrap |
| Traffic SC previous-period | none | no | same property_id | `_traffic_date_range` / calendar | **no** | **no** `run_ga4_report` | no | overview copy |
| Traffic SC source/medium | none | no | same | dimensions hardcoded | **no** | **no** | no | “last 30 days” string |
| `_ga4_read_observation` (cross-source steps) | none | **step_id yes** | `resolve_resource` | `_traffic_date_range` | **no** | **no** | **yes** | later compose |
| `_gsc_read_observation` | GSC query (F1 key if via invoke) | step_id | GSC resolver | own | **not via HMAC invoke** | direct connector | **yes** | later |
| `post_publish_marketing_metrics_service` | none | n/a (background metric) | campaign decode | hardcoded 7daysAgo | **no** | **no** | no | n/a (not cognitive chat) |
| `tool_service._exec_analytics_reports_run` | executor under invoke | if F1 enforce | params | params | **yes if F1 invoke** | N/A (is executor) | NormalizedResult | n/a |

### Proposed 2.0-A cohesion (approval required — not started)

| Candidate | Problem | Evidence | Owner | Files | Migration | Tests | Latency | Rollback | Gate |
|-----------|---------|----------|-------|-------|-----------|-------|---------|----------|------|
| Compile-before-strategy | ReAct `tool_choice=auto` after E4 still picks raw tools | `react_engine.py` ~989; `narrow_tools_for_turn` heuristic | Runtime | `react_engine`, `agent_intelligence`, optimizer | Eligible ActionSpec set before model | goldens A–G + one CRM READ unit | no extra LLM if reuse compile | flag | UNIT_TEST; live optional if EXTERNAL_BLOCKED |
| SC companion HMAC | period/source/geo variants skip proof | analytics service 392, 711–725 | Runtime | `analytics_traffic_overview_service` | Same `preflight_read_action`+`invoke_tool` or drop companion | companion HMAC test | +1–2 preflight ms | keep primary HMAC | UNIT_TEST |
| SC de-dupe time/resource/prose | second compiler + “last 30 days” | copy at ~760 vs compiled calendar | Runtime | traffic service, Composer | consume proof.time_window only | golden last-month copy | none | flag | UNIT_TEST |
| ReAct under compiled-eligible | harness should own implementation | non-F1 tools skip preflight | Runtime | `react_engine`, `read_preflight` | F1-or-spec flag before invoke | ReAct F1 + non-F1 | same | flag | UNIT_TEST |
| Composer-only | `Stopped.` SSE + CI red | `assistant.py:855–859`; CI 35283284249 | Runtime | `assistant.py`, composer | compose `kind=stopped` | bypass scanner green | none | revert SSE | CI green on those tests |
| Plan/step lineage | invoke may use `run_id` not plan | `tool_service` meta; ReAct optional | Runtime | `tool_service`, react, SC | require plan/step on cognitive invoke | lineage unit | none | synthetic single-step | UNIT_TEST |

**Out of 2.0-A:** WRITE architecture, voice latency, entity join, recipe explosion, CI lint dict-coercion (unless blocking merge confidence; not execution SoT).

---

PLATFORM-WIDE EXECUTION 2.0 SPEC READY: **YES** (spec/plan only)

**2.0-A0 COMPLETE:** **YES** (architecture + CI named failures + `/health`; live connector probes **EXTERNAL_BLOCKED** / **NOT_RUN**)

**READY TO BEGIN 2.0-A:** **NO** until human review of this A0 report.

TOP P0 ARCHITECTURAL PRIORITY: **Close competing execution cores on the traffic/F1 island (HMAC companions, Composer-only prose, compile-before-strategy) while live-proving current F1/SC — without touching WRITE authorization.**

FIRST RECOMMENDED IMPLEMENTATION PHASE: **2.0-A Cohesion** (after approval). Do not start automatically.

WHY: Compiler is **TEST_PROVEN** and **STRUCTURAL_IN_IMAGE** `f4accdfc` (`/health` `2026-09-18T07:06:51Z`). It is **not LIVE_USER_PROVEN**. CI red is named (Composer `Stopped.` bypass, lint, overlap-guard, Anthropic fixture). SC companions still bypass HMAC. ReAct still owns implementation choice for non-SC operational READs.

**Stop for review. Do not implement 2.0-A until approved.**

# Gravitre Autonomous Execution Re-Audit 2.0

**Status:** AUDIT ONLY — no 2.0 implementation in this pass  
**Date:** 2026-09-18  
**Method:** Current `main` code + catalog recount + production `/health` + GitHub Actions. Live chat/voice/tool traces were **not** re-run.  
**Prior audits (disposition only):** [gravitre-autonomous-business-execution-audit-2026-09.md](./gravitre-autonomous-business-execution-audit-2026-09.md), [connector-action-wiring-audit.md](./connector-action-wiring-audit.md)

**Do not treat this document as LIVE_USER_PROVEN.** Where a claim lacks a conversation/run/`audit_events` pointer, the label stays CODE_ONLY, UNIT_TEST, or NOT RUN.

No customer-facing prices, Certified/TRAINED badges, or Enable toggles are proposed.

---

## 0. Primary answer

Gravitre is **closer to a business-task compiler on a thin F1 READ slice** (five catalog actions + HubSpot search schema class + traffic short-circuit) and **still a capable NL router with fork-dependent execution** everywhere else.

A user can say “website traffic last month” and, **on the analytics short-circuit + F1 preflight path**, the platform can: detect capability, compile a calendar month, bind a unique tenant domain to a GA4 property (when unique), refuse to ask for `property_id`, attach only executable tools, and HMAC-bind invoke. That path is **TEST_PROVEN** (`test_golden_benchmark_traffic.py`) and **structurally present in production image `f4accdfc`**. It is **not LIVE_USER_PROVEN** in this pass (no `conversation_id` / `audit_events` pointer collected here; isolated-org golden live smoke artifact absent).

The same user asking “which deals need attention,” “who owes us money,” “send Sarah the proposal,” or “why did pipeline fall” still **largely lands on ReAct / model args** except where a new capability (`crm.deals.read`, `finance.invoices.read`, `support.tickets.read`) plus F1 keys apply. Writes remain **intentionally ungated by F1** and still require enterprise approval.

**Manus-like operator:** **PARTIAL** — strong compiler island, not platform-wide autonomy.

---

## PART 1 — Baseline current state

| Item | Value | Evidence class |
|------|-------|----------------|
| Local HEAD | `dcc2324b` (docs-only certification process) | git |
| `origin/main` | `dcc2324b` | git |
| Production `/health` `git_sha` | **`f4accdfc79a0c2ef096e759d0954e7153bd58877`** | `https://api.gravitre.app/health` @ `2026-09-18T06:28:02Z` (same SHA on Railway origin health) |
| Runtime in prod vs HEAD | Prod is **one commit behind** HEAD; delta is process docs only | git log |
| Relevant deploy | Railway backend production **success** for execute-now push `35282413007` | GitHub Actions |
| Merge CI | **Red** on main (Backend pytest + Web lint/typecheck/build). Latest: [35283284249](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35283284249). Same failure class across F1/golden/execute-now tips — **not introduced uniquely by F1**. | GitHub |
| Unified LIVE flags in prod | `unified_turn_live_enabled=true`, shadow on, embedding retrieval on | `/health` JSON |
| Golden live smoke JSON | **Missing** (`docs/delivery/smoke-golden-benchmark-live.json` not in tree) | NOT RUN |

### E1–E5 / F1 in the production image (`f4accdfc`)

| Phase | Structural status | Production evidence | Remaining gap | Owner |
|-------|-------------------|---------------------|---------------|--------|
| E1 semantic / resource | **IMPLEMENTED** in prod image (resolution pipeline, domain bind `b4609c0a`) | CODE_ONLY + UNIT_TEST. Live `resolution_reason=tenant_domain_binding` **NOT RUN** | Multi-property orgs without unique domain still clarify | Runtime / catalog |
| E2 tracing | **IMPLEMENTED** (`compiled_task` linked on trace) | CODE_ONLY. Prod trace with `compiled_task` **NOT RUN** | Uniform Observation object still PARTIAL | Runtime |
| E3 clarification | **IMPLEMENTED** policy + engine | UNIT_TEST (golden C/D). Prod clarify copy **NOT RUN** | ReAct model can still ask avoidable questions off SC | Runtime |
| E4 ContextCompiler | **IMPLEMENTED**; `compiled_task` slice **IMPLEMENTED** (`6245e4cb`) | CODE_ONLY. Prod `compiled_task_included` **NOT RUN** | Token/latency of compiler **UNKNOWN** this pass | Runtime |
| E5 ExecutionPlan | **IMPLEMENTED** reconcile + analytics recipe plan | CODE_ONLY / UNIT_TEST. Complex-task plan lineage **NOT RUN** | Execution outside plan still possible (Intent Gateway, IH deterministic) | Runtime |
| F1 READ preflight | **IMPLEMENTED** five keys + HMAC invoke enforce | UNIT_TEST. Live Google/QBO/Zendesk **EXTERNAL_BLOCKED** on isolated org historically | Slice does not scale to 732 actions | Catalog / preflight |
| F2 READ repair | **IMPLEMENTED** one-shot sibling/GSC fallback | UNIT_TEST | Post-provider failures still weak | Runtime |
| ReAct READ preflight | **IMPLEMENTED** `react_preflight_args` when `is_f1_read_action` | CODE_ONLY | Non-F1 ReAct still model→provider | Runtime |
| `invoke_tool` preflight | **IMPLEMENTED** `enforce_invoke_preflight` for F1 only | CODE_ONLY | Non-F1 unprotected | Runtime |
| Canonical time | **IMPLEMENTED** `canonical_time_resolver.py`; SC uses it | UNIT_TEST golden A | Non-F1 / model dates still LLM | Runtime |
| Domain→resource | **IMPLEMENTED** `domain_property_binding.py` | UNIT_TEST golden B | Live multi-property **NOT RUN** | Runtime |
| Action availability attach | **IMPLEMENTED** `CAN_THIS_ACTION_EXECUTE_NOW` (`f4accdfc` **in prod**) | UNIT_TEST. Live attach omission **NOT RUN** | Cheap snapshot; not per-action HubSpot scopes | Runtime |
| Parameter provenance | **IMPLEMENTED** on F1 `ParameterSourceRule` | UNIT_TEST | Ledger still write-centric | Catalog |
| Provider constraints | **PARTIAL** | CODE_ONLY | GA4 combos still mostly executor | Catalog |
| Plan/step observation | **PARTIAL** | CODE_ONLY | HMAC proof carries plan/step on F1; not all paths | Runtime |
| ActionSpec canonicalization | **PARTIAL** F1 + HubSpot search class (`5881f5b2`) | UNIT_TEST | 732-action trinity remains | Catalog |
| Trusted preflight / stale | **IMPLEMENTED** HMAC on F1 | UNIT_TEST | Non-F1 no proof | Runtime |
| compiled_task | **IMPLEMENTED** projection | CODE_ONLY | Not a BusinessTask runtime; live persist **NOT RUN** | Runtime |
| Certification states | **PROCESS ONLY** (`dcc2324b`, not required in runtime image) | docs | No DB enum (intentional) | Product/process |

---

## PART 2 — Original root-cause audit disposition

Source: `gravitre-autonomous-business-execution-audit-2026-09.md` (2026-09-17). Reclassified against **current code**.

| Old finding | Disposition | Evidence |
|-------------|-------------|----------|
| Execution semantics differ by routing fork (Invariant I) | **PARTIALLY_FIXED** | Analytics SC now compiles calendar month + F1 preflight (`analytics_traffic_overview_service._traffic_date_range` + `preflight_read_action`). LIVE still **forced off** when `analytics_short_circuit` (`agent_intelligence.py` ~3212–3219). Fresh single-connector still **ReAct-first** (`should_run_connector_preflight` docstring + `return is_orchestration_intent`). Intent Gateway / IH deterministic still skip compiler. |
| Resolution computed but not consumed before ReAct | **PARTIALLY_FIXED** | `compiled_task` projected and fed to ContextCompiler. ReAct invoke still only compiles F1 keys. |
| API-required treated as user-required on ReAct | **PARTIALLY_FIXED** | F1 advertised `required: []` for resolver-owned fields (`PHASE_SCHEMA_CONVERGENCE.md`). Non-F1 unchanged. Golden F overwrites model-guessed `property_id` — UNIT_TEST. |
| No canonical business-task contract | **PARTIALLY_FIXED** | `compiled_task` is a **read-only projection**, not an ingress BusinessTask that gates dispatch. |
| Time language not compiled (“last month” → 30d) | **PARTIALLY_FIXED** | Resolver compiles previous calendar month when the phrase is present. Default without phrase remains `30daysAgo`. User copy can still say “last 30 days” for top source after a calendar window (`analytics_traffic_overview_service.py` ~760). Off-slice still model. |
| Business identity does not feed resources | **PARTIALLY_FIXED** | Tenant domain bind (`PHASE_DOMAIN_PROPERTY_BINDING.md`). Identity still does not compile `property_id` via `BUSINESS_IDENTITY` source (intentional). Live unique-bind **NOT RUN**. |
| Capability-first vs connector-first hybrid | **STILL_PRESENT** | 13 capabilities (was 9). ReAct still connector tool names. Traffic recipe optional GSC — CODE_ONLY. |
| Source discovery not passed to tool_choice | **PARTIALLY_FIXED** | `CAN_THIS_ACTION_EXECUTE_NOW` drops disconnected vendors before attach. Capability recipe still thin. |
| Resource resolver not at invoke | **PARTIALLY_FIXED** | F1 `preflight_read_action` + `enforce_invoke_preflight`. Non-F1: adapter or `resolver_not_implemented`. |
| No parameter compiler | **PARTIALLY_FIXED** | F1 `ParameterSourceRule` compiler. Writes still ledger/schema_param_extractor. |
| Preflight missing on ReAct | **PARTIALLY_FIXED** | F1 only. `should_run_connector_preflight` still false for fresh single-connector. |
| E3 avoidable property-ID / domain | **PARTIALLY_FIXED** | Golden B/C/D UNIT_TEST. Live **NOT RUN**. |
| Task continuity / “that” | **STILL_PRESENT** as class | `active_analysis` / `reference_resolver` / `execution_plan` still multiple stores. Multi-turn live **NOT RUN**. |
| Retrieval/web_search when no GA | **PARTIALLY_FIXED** | Golden E: connect guidance, no web-search detour — UNIT_TEST. |
| Self-repair absent | **PARTIALLY_FIXED** | F2 one repair; transport retries; no general argument repair after provider 4xx. |
| Multi-source GA4+GSC special-case | **PARTIALLY_FIXED** | Recipe + `search.performance` capability; GSC **not** a second exclusive vendor on `analytics.traffic_overview`. Live dual-source **NOT RUN**. |
| Response abstraction leaks | **PARTIALLY_FIXED** | Composer still SoT; `assistant.py` still yields `sse_text_delta(..., "Stopped.")` — **LEGACY bypass**. |
| `_ga_property_id` leak | **SUPERSEDED** on F1 primary invoke | HMAC enforce on `invoke_tool` F1 keys. Traffic SC **companion** `run_ga4_report` (PoP + source breakdown) still **BYPASSED** (no second seal). |
| 30d hard-code as only window | **SUPERSEDED** | Default when **no** time phrase; “last month” compiled. |

---

## PART 3 — Connector action recount (live Python 2026-09-18)

`audit_connector_catalog()` / `get_vendor_catalog()` / `list_capability_ids()` — **did not write** audit JSON this pass. Stale file still shows `verifiedWorking: 482`; **live recount differs**.

| Metric | Previous audit JSON | **This pass (code)** |
|--------|--------------------:|---------------------:|
| Catalog vendors | 85 | **85** |
| Catalog actions | 732 | **732** |
| Implemented / executable | 730 | **730** |
| Catalog-only ghosts | 2 | **2** (`webhook.connectors.get`, `webhook.post.replay`) |
| Test `verifiedWorking` | 482 | **492** |
| Implemented unverified / noTests | 248 | **238** |
| Chat/execute exposed | 730 | **730** |
| Registry violations | 0 | **0** (from last JSON; not re-scanned for new violations beyond summary) |
| Canonical capabilities | 9 | **13** |
| Resource adapters | 8 + GA4 | **9** in `RESOURCE_ADAPTER_REGISTRY` including **zendesk** + **GA4 special-case** (not in that dict) |
| Resource-aware vendors | 9/85 | **Split SoT:** health matrix lists **9** (`github`, `google_ads`, `google_analytics`, `google_search_console`, `hubspot`, `microsoft365`, `quickbooks`, `salesforce`, `slack` — **zendesk omitted**). `ActionSpec.resource_requirements` non-empty on **5** F1 vendors only. |
| Capability-mapped actions | ~9 bindings | **13** defs; **23** `VendorCapabilityBinding` rows; **22** unique action keys; `ActionSpec.capabilities` non-empty on **5** F1 specs only |
| Preflight protected | ~0 ReAct | **5 F1 READ keys** (+ HubSpot search **schema** class, not HMAC slice) |
| Canonical-schema compliant | FAIL platform | **F1 + HubSpot search** only (`canonical_action_schema.py`) |
| Parameter-source compliant | FAIL | **F1 `ParameterSourceRule` only** |
| Provider-constraint aware | FAIL | **STILL_PRESENT** as class |
| Production verified (evidence-linked) | 482 tests mislabeled | **UNKNOWN / NOT RUN** this pass — tests ≠ prod |

Certification process: [connector-certification-states.md](./connector-certification-states.md). **No runtime distribution by Track A state** (intentional — no enum).

---

## PART 4 — ActionSpec canonicality

**Required:** zero `COMPETING_SOURCE_OF_TRUTH` on **migrated** paths.

| Source | Classification | Notes |
|--------|----------------|-------|
| Catalog `ActionSpec` via `get_action_spec()` | **SoT** | Option B materialize F1 overlays at catalog build (`f1_read_slice.py`) |
| `resolve_action_schema` / `input_schema` | **PROJECTION** on F1+HubSpot search | Schema convergence |
| `workflow_schema` / `get_workflow_schema` | **PROJECTION** on migrated; **LEGACY/COMPETING** elsewhere | Gate still used for governed writes |
| `action_parameters.py` batch | **LEGACY** off-slice | Must not be SoT for F1 |
| Executor-only guards | **VALID_PROVIDER_GUARD** if they reject what schema forbids; **COMPETING** if they require fields schema omitted — HubSpot search class **fixed** UNIT_TEST |
| MCP tool schema | **COMPETING / inferred** | Not F1 HMAC |
| Partner SDK inputSchema | **COMPETING** at ingest | Track C |
| `catalog_http` inference | **LEGACY** | Long-tail |
| ReAct model assumptions | **COMPETING** for non-F1 | Model fills JSON Schema |
| Hard-coded handler report body | **PROJECTION** of F1 compile on traffic SC after `preflight_read_action` | Dates from proof / time resolver |

**Migrated paths (F1 five + HubSpot search advertised schema): COMPETING_SoT = 0 by contract (UNIT_TEST).** Platform-wide: **COMPETING still dominant**.

---

## PART 5 — Preflight coverage matrix

Canonical F1 preflight = `preflight_read_action` + HMAC `ToolContext.preflight_result` + `enforce_invoke_preflight`.

| Route | Canonical F1 preflight? | Notes |
|-------|-------------------------|-------|
| Analytics traffic SC | **Primary** GA4 report: yes | Handler `preflight_read_action` then `invoke_tool` with proof. **BYPASSED:** companion `run_ga4_report` for previous-period + source breakdown (`analytics_traffic_overview_service.py` ~711–725) — no second HMAC seal |
| ReAct tool loop | **Yes iff** `is_f1_read_action` | `react_engine.py` ~900 |
| `invoke_tool` | **Yes iff** F1 | `tool_service.py` ~4722 |
| Unified LIVE | **No F1 compile as gate** | Model tools; LIVE disabled on analytics SC |
| Classical ReAct | Same as ReAct | Dual path remains |
| Governed `action_selection_gate` | **Yes iff** F1 | Else workflow schema |
| Direct connector Python (GA4 after SC) | After F1 proof on SC | Other direct adapters **UNPROTECTED** |
| Workflow canvas | Gate / run authority | Not F1 HMAC unless action is F1 |
| Agent delegation | Same `execute_task_streaming` / ReAct | F1 only |
| Voice `spoken_mode=True` | **Same kernel** | Pipecat → `execute_task_streaming` — modality not a second compiler |
| Intelligence Hub deterministic | **No** | Shortcut |
| Scheduled / Temporal jobs | **UNKNOWN** this pass | Not traced |
| Background automations | **UNKNOWN** | |
| MCP | **ActionSpec via catalog sync; no F1 HMAC** | `mcp_catalog_sync` builds specs; execute uses write-approval hints only |
| Partner SDK | **No** | |
| catalog_http | **F1 keys only** | Shares `invoke_tool` gate; non-F1 catalog_http unprotected |
| Webhook triggered | **No** (ghosts unimplemented) | |
| `CAN_THIS_ACTION_EXECUTE_NOW` | **Not preflight** | Attach-time vendor snapshot only |

**Verdict:** F1 established a **scalable architecture** (ActionSpec rules + HMAC + invoke enforce) but **only instrumented five READs**. It did **not** make the platform preflight-safe.

---

## PART 6 — READ coverage

| Class | What |
|-------|------|
| **PREFLIGHT_PROTECTED** | Five F1 keys on `invoke_tool` / ReAct / gate. **Exception:** traffic SC companion GA4 reports are **BYPASSED**. |
| **LEGACY_VALIDATED** | HubSpot search siblings (schema/list fallback, not F1 HMAC); governed workflow reads; availability on invoke |
| **UNPROTECTED** | Remaining ~725 catalog reads: model/inferred schema → `invoke_tool` without HMAC |
| **UNKNOWN** | MCP/catalog_http edge params |

**Business-critical still UNPROTECTED examples:** Gmail list, Slack history, HubSpot contacts.search (schema class only), Salesforce queries, Stripe list, most GA4 sibling actions (`realtime.run`, etc.).

Model-generated args → provider **without canonical validation** remains the **default ReAct path** off-slice.

---

## PART 7 — WRITE lifecycle (unchanged by F1 — by design)

Trace still: NL → (optional capability `email.send` / `crm.contact.create` / `payment.refund`) → mapper/ReAct → risk (`catalog_write_authority`, 362 high_risk historically) → `react_write_gate` / pending confirmation → ExecutionPlan/pending_task → `invoke_tool` **without F1 HMAC** → observation → limited success_verification catalog.

**READ vs WRITE cognitive semantics:** **INCONSISTENT**. READs on F1 compile before provider; WRITEs still **approval-first, compile-partial**. That is **correct for enterprise governance**. Do **not** auto-execute financial/destructive/external comms.

| Class | Governance (code) | Autonomy |
|-------|-------------------|----------|
| Email send | WRITE + external; approval | Governed |
| CRM update | WRITE approval | Governed |
| Slack/Teams send | WRITE | Governed |
| Calendar create | `calendar.event.create` capability + write | Governed |
| Campaign change | typically WRITE; often ReAct | PARTIAL |
| Refund | `payment.refund` → Stripe | Governed |
| Invoice action | finance READ F1 list only; writes ungated by F1 | PARTIAL |
| Ticket change | Zendesk READ list F1; writes not F1 | PARTIAL |
| Document create | capability search ≠ create | PARTIAL |
| Destructive | high_risk / destructive hints | Must remain approval |

Live write traces **NOT RUN** this pass.

---

## PART 8 — Common-sense business language

| Phrase | Structural expectation | This pass |
|--------|------------------------|-----------|
| How did our website do last month? | Traffic SC + calendar month | **TEST_PROVEN** golden A |
| Which deals need attention? | `crm.deals.read` / HubSpot F1 search | **CODE_ONLY** recipe; live **NOT RUN**; likely still ReAct filters |
| Who owes us money? | `finance.invoices.read` F1 list | **CODE_ONLY**; QBO **EXTERNAL_BLOCKED** historically |
| What's causing support volume to increase? | `support.tickets.read` ≠ causal handler | **MISSING** diagnostic compiler |
| Who am I meeting tomorrow? | calendar READ not F1 | **UNPROTECTED** / model |
| Send Sarah the proposal we discussed | `email.send` + memory/entity | Governed write; entity **PARTIAL** |
| Tell the sales team the meeting moved to 3 | messaging WRITE | Governed; time compile **not** F1 |
| Why did pipeline fall this month? | Multi-source diagnostic | **MISSING** |
| Anything important today? | Proactive / digest | **WEAK** / IH + signals **PARTIAL** |

Unnecessary questions: still expected off-slice (which HubSpot object, which mailbox). On-slice: property ID / rolling-30d-as-last-month should be **gone** if SC hits — UNIT_TEST, not LIVE_PROVEN.

---

## PART 9 — Business object understanding

No single BusinessObject graph type. Mapping is **capability + connector resource + `org_entity_resolution_records` (exact/alias) + Memory HMAC mentions**.

| Language | Maps toward | Converged? |
|----------|-------------|------------|
| our website | GA4 property / GSC site via domain bind | **PARTIAL** (unique host only) |
| that customer / John | entity_resolution + mentions | **PARTIAL** — not fuzzy `"Sarah"`↔`"Sarah Smith"` via Memory alone |
| the invoice | QBO F1 list | **SLICE only** |
| our pipeline | HubSpot deals F1 | **SLICE** |
| the campaign | ads adapter exists; no campaign capability | **WEAK** |
| those leads | Apollo/HubSpot ReAct | **WEAK** |
| Company, Employee, Contract, Incident, Objective, Metric, Workflow, Agent | scattered KG / product objects | **NOT a canonical ontology** |

**Entity/resource/business-object resolution is not fully converged.** Cross-system identity (CRM account = billing customer = Zendesk org) remains **MISSING** as a join layer.

---

## PART 10 — ContextCompiler (E4/F1)

**IMPLEMENTED:** `compiled_task` INCLUDE/EXCLUDE; chitchat empty projection excluded; no HMAC/property ids in user block (`PHASE_CONTEXT_COMPILER_COMPILED_TASK.md`).

**This pass did not measure** token cost, latency, or production `context_sources_included`.

Risks that remain **architecturally plausible:** duplicate RAG + compiled_task + org_context; LIVE vs classical two compile functions; stale `compiled_task` if patch bypassed (mitigated by `enrich_task_state_patch` reproject).

**Verdict:** Enough **structure** for traffic tasks; **UNKNOWN** quality under load.

---

## PART 11–12 — Multi-turn and references

**NOT RUN** live conversations A–D.

Structural: `execution_plan`, `pending_task`, `active_analysis`, `previous_option_set`, `compiled_task`, `resolution_trace` — **still multiple frames**. Follow-ups like “yes / instead / last one” depend on `reference_resolver` + pending family. Risk of **raw LLM guessing** when analytics SC does not re-trigger remains **STILL_PRESENT**.

---

## PART 13–15 — Reasoning, decomposition, cross-system

No causal “why pipeline declined” compiler. Cross-source **website** plan exists (GA4+GSC recipe). CRM+support+billing joins **ABSENT**. Parallel safe READs exist for that recipe + orchestration; **not** general Manus decomposition.

Delegation: parent/child plans **CODE_ONLY**; whether roles add expertise vs extra LLM **UNKNOWN** this pass.

---

## PART 16–17 — Retrieval hierarchy / knowledge vs live

Analytics SC still prefers connectors over KB (`should_suppress_knowledge_base_for_turn` class). Golden E UNIT_TEST: no web-search detour when analytics disconnected.

**Refund policy vs refunds this week:** no dedicated source-class compiler; likely RAG vs Stripe/QBO fork — **UNKNOWN** live.

Public web winning over live systems: **PARTIALLY_FIXED** for traffic language; **STILL_PRESENT** risk for other operational asks.

---

## PART 18 — Self-repair after valid preflight fails

F1 prevents many **invalid** calls. After a **valid** provider failure:

| Class | Current |
|-------|---------|
| TRANSIENT | invoke_tool retries (~2) |
| RATE_LIMIT | classified; backoff partial |
| AUTH | STA-303 / F2 GSC fallback if connected |
| RESOURCE_CHANGED | **WEAK** |
| SCHEMA_DRIFT | **WEAK** off-slice |
| PROVIDER_CONSTRAINT | executor error → user |
| EMPTY/PARTIAL_DATA | model prose |
| WRONG_TOOL | F2 HubSpot list sibling **one shot** |
| WRONG_SOURCE | F2 GA4→GSC |
| CONFLICTING_DATA | **ABSENT** |

Human ask still the default off-slice.

---

## PART 19 — ExecutionPlan quality

E5 reconcile **IMPLEMENTED** (`reconcile_execution_plan`). ReAct still takes optional `plan_runtime`; plan id is stamped only when it is set (`react_engine.py`). Execution **can run without plan lineage**. Intent Gateway, IH deterministic, and some LIVE text also sit outside. Complex-goal plans **NOT RUN**.

---

## PART 20–21 — Delegation and workflows

Workflows remain a **parallel automation architecture** with canvas write authority. Conversation can invoke workflows historically; **observe → replan in same compiler** is **PARTIAL**. Not first-class ExecutionPlan strategy for all automations.

---

## PART 22 — Text experience

Composer is intended SoT. Residual `sse_text_delta("Stopped.")` in `routers/assistant.py`. Infrastructure vocabulary reduced on SC path (golden G: Analytics/Search not vendor names — UNIT_TEST). Latency/formatting **NOT RUN**. Dual surfaces `/ai` and `/agents/[id]/chat`: **frontend** shares Gravitre AI workspace (Phase 1A comment: not a second live chat runtime); backend still one `execute_task_streaming` with agent scope. **Until one runtime is proven live**, treat as **COMPATIBILITY** not fully merged.

---

## PART 23–28 — Voice

**Architecture:** Pipecat / `voice_session_service` → `execute_task_streaming(spoken_mode=True)`. Comment in `agent_intelligence.py`: same LIVE path, not a fork; analytics SC still disables LIVE the same as text.

**Voice-specific forks that can differ:** speculative generation/prefetch; `voice_context_overlap_v1`; TTS chunking; spoken conversational gate; STT errors.

**Comprehension, barge-in, voice-to-voice, p50/p95, text↔voice continuity:** **NOT RUN** this pass. Classify **UNKNOWN**. Cancellation: `AgentExecutionInterrupted` / interrupt enforce exists in `invoke_tool` — CODE_ONLY.

**Must not claim voice = text LIVE_PROVEN.**

---

## PART 29–30 — Latency and model routing

Prod: `unified_turn_task_model_tier=low`. No p50/p95 collected.

Known serial risks (prior audits, not re-measured): `force_live` connector probes, embedding tool retrieval, ContextCompiler, dual compile when LIVE then SC. Execute-now **avoids** per-tool live probes.

Model routing opportunities: deterministic F1 compile already **no-model** for params; classification vs planning still often one model. **Do not change models in 2.0 without measurement.**

---

## PART 31–33 — Memory, learning, proactive

Memory Phase 1: opaque HMAC **exact** mention match — **not** fuzzy person join. KG + `org_entity_relationships` exist. Outcome learning loop LEARN in cognitive loop — **PARTIAL**, not closed-loop business impact.

Proactive: connector health jobs succeed on schedule; productized “don’t be noisy” anomaly operator **WEAK**. Do not invent customer alert SKUs.

---

## PART 34 — Capability ontology (current 13)

`analytics.query`, `analytics.traffic_overview`, `search.performance`, `crm.contact.create`, `crm.contact.search`, `crm.deals.read`, `calendar.event.create`, `document.search`, `email.send`, `finance.invoices.read`, `messaging.channel.post`, `payment.refund`, `support.tickets.read`.

| Department | Coverage |
|------------|----------|
| Sales | PARTIAL (contact/deals) |
| Marketing | WEAK (traffic/search only; no campaign capability) |
| Finance | PARTIAL (invoice **read** F1; refund write capability) |
| Support | PARTIAL (ticket **list** F1) |
| HR / Legal / Procurement / Product / Engineering | WEAK / ReAct |
| IT / Security | gravitre_managed knowledge **PARTIAL** |
| Executive / Ops | WEAK |

Business intents without recipes **still fall to flat ReAct**.

---

## PART 35–37 — Connector readiness, certification, generated connectors

OAuth healthy ≠ ready (process Track A vs B). Priority connectors: HubSpot/Slack/GA4/GSC have tests in audit counts; Confluence-class still `no_tests`. F1 live Google/QBO/Zendesk **EXTERNAL_BLOCKED** on isolated org.

MCP / SDK / catalog_http: **not equivalent** ActionSpec+HMAC+capability+tests. **Architecture bypasses remain.**

Certification **process** defined; **distribution by state not in code**.

---

## PART 38 — Write governance

READ auto-execute: F1/SC yes when compiled. Low-risk WRITE / external / financial / destructive / HR: **must remain gated**. `catalog_write_authority` has **no financial class** — `kind` / `destructive` / `requires_approval` / scopes (~362 gate-true). Tenant isolation on domain bind: same-org only (UNIT_TEST). **Do not recommend unsafe auto-WRITE.**

---

## PART 39 — Response quality

SC canned answers: business language UNIT_TEST. ReAct: variable. Fake certainty still a composer/policy risk. Tool logs in user text: **PARTIAL** leak class.

---

## PART 40 — COMMON_SENSE_GAP inventory

| ID | Gap | Status after E1–F1 |
|----|-----|-------------------|
| CS-1 | Asks for GA4 property ID | **Should be gone** on F1/SC — UNIT_TEST; live **NOT RUN** |
| CS-2 | “Last month” = 30 days | **FIXED** when phrase present; default 30d if no phrase |
| CS-3 | Asks which system when only one fits | **PARTIALLY_FIXED** execute-now + capability route |
| CS-4 | Web search instead of connect analytics | **PARTIALLY_FIXED** golden E |
| CS-5 | search vs list (HubSpot deals) | **PARTIALLY_FIXED** F2 listing repair |
| CS-6 | Cannot infer “our site” | **PARTIALLY_FIXED** unique domain bind |
| CS-7 | Forgets “that” | **STILL_PRESENT** class |
| CS-8 | Asks data already in compiled_task | **UNKNOWN** |
| CS-9 | Success before work finished | SSE/terminal policy **PARTIAL** |
| CS-10 | Requires connector name | **PARTIALLY_FIXED** traffic; **STILL_PRESENT** other depts |
| CS-11 | Minor tool error → dead end | **PARTIALLY_FIXED** F2 only |
| CS-12 | Causal “why” with one connector | **STILL_PRESENT** |
| CS-13 | Cross-system customer identity | **MISSING** |
| CS-14 | Voice disfluency / barge-in | **UNKNOWN** |
| CS-15 | Dual `/ai` vs agent chat semantics | Frontend converged; **prove live** |

---

## PART 41 — Cohesion / duplication

| Duplication | Class |
|-------------|-------|
| LIVE vs classical vs analytics SC vs ReAct vs governed connector | **COMPETING_ARCHITECTURE** (SC is still an architectural leak **and** the best compiler island) |
| `pending_task` vs ExecutionPlan | **COMPATIBILITY** / E5 in progress |
| `action_parameters` vs ActionSpec | **LEGACY** off-slice; **PROJECTION** on-slice |
| Two chat routes | **INTENTIONAL_ADAPTER** (same workspace) |
| Voice speculative vs kernel | **COMPATIBILITY** |
| Intent gateway canned vs compiler | **LEGACY** high-confidence skip |
| `sse_text_delta` Stopped | **LEGACY** |
| Availability service vs execute-now vs F1 preflight | **INTENTIONAL_ADAPTER** (different layers) |

---

## PART 42 — Evidence legend for major claims

| Claim | Evidence |
|-------|----------|
| Prod runs execute-now + F1-era SHAs | PRODUCTION_TRACE: `/health` `f4accdfc` @ 2026-09-18T06:28:02Z |
| Calendar month + F1 compile | UNIT_TEST golden A |
| Domain bind | UNIT_TEST golden B |
| Connect guidance no web search | UNIT_TEST golden E |
| Catalog 732/730/492/238 | CODE_ONLY recount 2026-09-18 |
| Live traffic / QBO / Zendesk / voice | **NOT RUN / EXTERNAL_BLOCKED** |
| CI green | **false** — merge CI failing |
| Isolated golden live smoke | **NOT RUN** (no artifact) |

---

## PART 43 — Manus-like 2.0 gap matrix

Ratings: STRONG / FUNCTIONAL / PARTIAL / WEAK / ABSENT. Evidence in parentheses.

| Characteristic | Rating | Evidence |
|----------------|--------|----------|
| goal-first interaction | PARTIAL | capability router + SC; ReAct tool-first |
| business-object understanding | WEAK | no canonical object model |
| commonsense | PARTIAL | traffic island only |
| context | PARTIAL | E4 + compiled_task CODE_ONLY |
| task continuity | PARTIAL | multiple state keys |
| reasoning | WEAK | no causal multi-source compiler |
| planning | PARTIAL | E5 + orchestration |
| tool selection | PARTIAL | execute-now + still model off-slice |
| resource discovery | PARTIAL | ~10/85 adapters + domain bind |
| parameter completion | PARTIAL | F1 only |
| read execution | PARTIAL | 5 HMAC + rest legacy |
| write execution | FUNCTIONAL | governed, not autonomous |
| governance | STRONG | write gates preserved |
| self-repair | WEAK | F2 one-shot |
| multi-source reasoning | PARTIAL | GA4+GSC recipe |
| cross-department | WEAK | 13 capabilities |
| entity joins | ABSENT | no CRM=billing=Zendesk |
| memory | PARTIAL | exact HMAC |
| learning | WEAK | loop LEARN |
| proactive | WEAK | health jobs ≠ operator |
| text UX | PARTIAL | composer + Stopped leak |
| voice comprehension | UNKNOWN | not tested |
| voice execution | UNKNOWN | same kernel CODE_ONLY |
| voice latency | UNKNOWN | |
| barge-in | UNKNOWN | interrupt primitives CODE_ONLY |
| text/voice parity | PARTIAL | intended same path |
| connector extensibility | PARTIAL | catalog strong; generated weak |
| observability | PARTIAL | E2 + health SHA |
| business-level responses | PARTIAL | SC good |

---

## PART 44 — Regression

| Area | Regression this pass? |
|------|------------------------|
| E1–E5 primitives | **No evidence of removal** |
| F1 slice | **Preserved** |
| WRITE/G8 | **Not redesigned** (intentional) |
| CI | **Still red** — pre-existing class on main; **not proven F1-caused** |
| Dual LIVE vs SC | **Still a fork** (analytics_short_circuit disables LIVE) — not a new defect |
| `sse_text_delta` Stopped | **STILL_PRESENT** LEGACY |
| Newly broken user path | **UNKNOWN** without live battery |

---

## PART 45 — Preserve (healthy enough)

- F1 ActionSpec + HMAC invoke proof + stale detection  
- Canonical time resolver + documented 30d default  
- Tenant-scoped domain bind (no cross-org)  
- Write approval / `react_write_gate` / canvas write authority  
- Response Composer as prose SoT (close remaining SSE leaks later)  
- STA-303 auth_expired vs tool_not_available taxonomy  
- Optional GSC on traffic recipe (not second exclusive vendor)  
- `CAN_THIS_ACTION_EXECUTE_NOW` attach gate (cheap, no `force_live` per tool)  
- Dual `/ai` workspace reuse (do not invent a third chat runtime)  
- Certification as **process**, not customer badge  
- Do **not** auto-WRITE  

---

## PART 46 — 2.0 priority map (do not implement here)

| Pri | Theme | Impact | Breadth | Deps | Regression |
|-----|--------|--------|---------|------|------------|
| **P0** | Keep WRITE/governance; fix CI standing red if it blocks deploy confidence; live-prove F1/SC on isolated org after SHA match | Safety + honesty | Platform | Secrets, Railway SHA | High if WRITE touched |
| **P0** | Close remaining composer/SSE bypasses; dual-path attach proof in prod | Reliability | Chat+voice | Composer owners | Medium |
| **P1** | Scale F1 architecture (preflight + source rules) beyond five READs **without** WRITE auto-exec | Autonomy | Connectors | ActionSpec SoT | High on ReAct |
| **P1** | One dispatch: tool_choice only after compile on operational asks (Invariant I) | Commonsense | All forks | compiled_task authority | High |
| **P2** | Expand capabilities/recipes (pipeline diagnostic, AR, tickets causal) | Reasoning | Depts | Ontology | Medium |
| **P2** | Entity join layer (customer identity) | Cross-system | CRM/billing/support | Memory Option B limits | High/PII |
| **P3** | Voice p50/p95 + barge-in + modality continuity measurements | UX | Voice | Same kernel | Medium |
| **P3** | ContextCompiler token/latency | UX | All | E4 | Medium |
| **P4** | MCP/SDK/catalog_http same harness; Track A certification as internal scorecard only | Scale | Generated connectors | Process doc | Medium |

---

## PART 47 — Document map

This file **is** the re-audit. Proposed 2.0 spec (not implemented): [GRAVITRE_PLATFORM_EXECUTION_2.0.md](../ai/GRAVITRE_PLATFORM_EXECUTION_2.0.md).

### Addendum — follow-up code evidence (same pass)

[F1 preflight coverage](d2069114-d5dd-41d2-b4be-2633897ebf99) and [catalog counts and writes](9b546a2e-c90e-4d17-bb6d-ae6f8ed12943) confirmed (no new live traces):

- Traffic SC **companion** GA4 reads (`run_ga4_report` PoP + source mix) skip HMAC.
- Copy can still say “last 30 days” after a calendar compile.
- Audit JSON has **no `generated_at`**; live `verifiedWorking` **492** vs file **482**.
- Ontology: 13 defs, 23 bindings, 22 unique actions; `ActionSpec.capabilities` on 5 F1 specs.
- Health-matrix `resource_aware` (9) **omits zendesk** even though an adapter exists.
- MCP: ActionSpec via sync; **no** `enforce_invoke_preflight`.
- ReAct `plan_runtime` optional → execution without plan lineage.
- Write gate is not a financial taxonomy.

---

## Final response block (review)

1. **Successfully fixed (structural / UNIT_TEST):** last-month calendar compile on F1/SC **when the phrase is present**; API-required vs user-required on F1 advertised schema; HMAC invoke for five READs (primary path); ReAct F1 preflight; domain unique-bind; compiled_task projection + compiler slice; traffic recipe optional GSC; HubSpot search advertised schema; execute-now attach; 13 capabilities.  
2. **Partially fixed:** fork semantics; resolution consumed; identity→resource; E3 avoidable asks; web-search vs connect; self-repair; multi-source; response abstraction; time copy vs compiled window.  
3. **Missed:** platform-wide preflight; BusinessTask ingress authority; entity joins; causal multi-source; WRITE compile parity (intentional); generated-connector harness; live proof; financial write class.  
4. **Regressed:** **none proven**. CI remains red (pre-existing class).  
5. **New defects (this pass, not 2.0 work):** traffic SC companion `run_ga4_report` **BYPASSED** HMAC; “last 30 days” copy after calendar window; execute-now dropping disconnected mentioned tools (intended); SC still disables LIVE (intentional); stale catalog JSON vs live 492.  
6. **Manus-like gaps:** compiler island vs router majority; 13 vs department coverage; no join layer; weak learning/proactive.  
7. **Text gaps:** SSE Stopped leak; ReAct vocabulary; dual route proof.  
8. **Voice gaps:** **NOT RUN** (latency, barge-in, STT, continuity).  
9. **READ gaps:** ~725 UNPROTECTED; SC companion GA4 **BYPASSED**; QBO/Zendesk/GA live **EXTERNAL_BLOCKED**.  
10. **WRITE gaps:** no F1; must stay governed.  
11. **Context/reasoning:** compiled_task unproven live; no diagnostic compiler.  
12. **Commonsense:** CS-7, CS-12–15 still open; CS-1/2/4 improved on-slice.  
13. **Self-repair:** F2 only; post-provider **WEAK**.  
14. **Latency:** **UNKNOWN** this pass; serial LIVE+SC+embed remain suspects.  
15. **Duplication:** COMPETING_ARCHITECTURE of SC/LIVE/ReAct/governed.  
16. **Top P0/P1:** live-prove F1/SC; don’t weaken WRITE; scale preflight architecture; unify compile-before-tool_choice; CI honesty.  
17. **Preserve:** list in Part 45.  
18. **2.0 direction:** **Strengthen the existing compiler** (ActionSpec + preflight + compiled_task as **authoritative ingress** + recipes). **Do not** add a parallel agent runtime or customer “Certified” chrome. Keep analytics SC until generic compile matches it, then fold SC into the same gate.  
19. **Production evidence still needed:** traffic conversation_id on `f4accdfc`+; `tenant_domain_binding` preflight; dual GA4+GSC plan; execute-now drop in audit; `compiled_task` persist; voice barge-in; golden live smoke JSON; CI green **or** documented standing-red owners.  
20. **RE-AUDIT COMPLETE:** **YES** as **CODE + UNIT_TEST + /health**. **NO** as **LIVE_USER_PROVEN** platform-wide.

**Stop for review. Do not implement 2.0 from this document without an explicit follow-on.**

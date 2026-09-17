# Gravitre Autonomous Business Execution Audit

**Status:** AUDIT ONLY — no fixes implemented  
**Date:** 2026-09-17  
**Scope:** Why Gravitre understands business language but fails to autonomously execute ordinary operational tasks  
**Related:** [platform-autonomous-execution-review.md](./platform-autonomous-execution-review.md), [connector-action-wiring-audit.md](./connector-action-wiring-audit.md)

---

## 1. Executive diagnosis

Gravitre **can parse** business language (Phase A semantic registry, capability router, analytics intent regex) but **cannot reliably compile** that language into a validated, resource-bound, parameter-complete tool invocation on every path.

The failure is **not primarily missing components**. E1–E5 primitives exist: canonical resolution, ContextCompiler, clarification policy, ExecutionPlan, resource resolver, parameter ledger, capability ontology, ReAct, governed connector execution, Response Composer.

The failure is **causal and structural**:

1. **Execution semantics differ by routing fork** — the same utterance can hit analytics short-circuit (preset GA4 report), unified LIVE (model-composed args), or ReAct (schema-inferred args with no property preflight). This is a **platform bug class** (Invariant I violation).

2. **Resolution results are computed but not always consumed** — Phase A produces `CognitiveResolutionResult` with `clarification` and `resource`, persisted in `resolution_trace`, but `agent_intelligence.py` does not gate ReAct/clarification on ambiguous resource **before** model turns. Clarification policy (E3) is wired in analytics handler and pipeline, not uniformly at dispatch.

3. **API-required ≠ user-required is violated on ReAct path** — `property_id`, `filter_groups`, report date ranges are **provider requirements** treated as **model/user obligations** when config/resolvers are not consulted at tool time (`tool_service._ga_property_id` vs `resolve_ga4_property`).

4. **No canonical business-task contract** — concepts exist scattered (`classification`, `capability_id`, `ExecutionPlan`, `active_analysis`, `resolution_trace`) but there is no single authoritative object representing objective + timeframe + capability + resource + compiled parameters **before** tool selection.

5. **Time language is not compiled** — "last month" is not mapped to calendar bounds before execution; analytics handler hard-codes rolling 30-day windows (`30daysAgo`→`today`). User expectation and system behavior diverge silently.

6. **Business identity does not feed resource selection** — org graph (`org_knowledge_nodes`, `entity_resolution_store`) does not map company website → GA4 property. Even connected GA4 with known domain may ask for property when OAuth multi-property link is pending.

**Bottom line:** Gravitre behaves like a **capable NL router with optional shortcuts**, not a **deterministic business-task compiler**. Manus-like autonomy requires **convergence of sequencing and contracts** on existing components — not a parallel subsystem.

---

## 2. Actual end-to-end request lifecycle

**Anchor query:** `"Tell me what my website traffic was last month."`

### Ordered flow (GA connected, property linked — happy path)

| # | Stage | Module | File : function | Input | Output | SoT | Bypass |
|---|-------|--------|-----------------|-------|--------|-----|--------|
| 1 | HTTP ingress | Web proxy | `apps/web/app/api/chat/route.ts` POST | User message | Backend SSE stream | JWT org | FASTAPI unset → 503 |
| 2 | Assistant API | Router | `routers/assistant.py` : `assistant_chat` | Messages, org | Stream generator | conversation row | killswitch |
| 3 | Ledger ingest | Module B | `assistant.py` pre-stream | User text | slot hints | parameter_ledger | — |
| 4 | Stream exec | Operator | `agent_intelligence.py` : `execute_task_streaming` | query, task_state | SSE events | task_state | IH deterministic |
| 5 | Intent Gateway | E? shortcut | `intent_gateway.py` : `evaluate_intent_gateway` | text | candidate or fallthrough | phrase bank | conf < 0.92 |
| 6 | Cognitive loop | Trace | `cognitive_loop_controller.py` : `begin` | turn meta | loop_id | audit | flag off |
| 7 | Phase A assess | E1 | `canonical_cognitive_resolution.py` : `assess_cognitive_resolution_needs` | text, connected | `CognitiveResolutionNeeds` | rules | chitchat skip resource |
| 8 | Phase A run | E1 | `cognitive_resolution_pipeline.py` : `run_cognitive_resolution` | needs | `CognitiveResolutionResult` | resolution_trace | `skip_resource` |
| 9 | Capability route | E1/E2 | `capability_router.py` : `route_capability_for_turn` | text, resolution | `analytics.traffic_overview` | CAPABILITY_REGISTRY | chitchat → None |
| 10 | E5 plan | E5 | `execution_plan_service.py` : `reconcile_execution_plan` | capability, connected | ExecutionPlan PARALLEL | task_state.execution_plan | confirm utterance reuse |
| 11 | Kernel pre-ACT | E2 | `cognitive_turn_kernel.py` : `run_pre_act` | ctx | RECALL/KNOWLEDGE | kernel sections | — |
| 12 | LIVE gate | Fork | `agent_intelligence.py` ~3157 | `analytics_short_circuit` | `_unified_live_ok=false` | flags | **forced off for GA traffic** |
| 13 | Preflight gate | Fork | `connector_chat_routing.py` : `should_run_connector_preflight` | task_state | false (fresh intent) | rules | pending/orch only |
| 14 | Context compile | E4 | `context_compiler.py` : `compile_assistant_turn_context` | classification | CompiledTurnContext | orchestrator | gateway exit |
| 15 | Orchestrator | E4 | `intelligence_orchestrator.py` : `prepare_assistant_turn` | turn ctx | RAG, signals, memory | context_registry | chitchat suppress |
| 16 | Clarification check | E3 | `clarification_engine.py` : `should_clarify` | message, trace | bool | rules + trace skip | resolved resource skip only |
| 17 | Analytics SC | Handler | `analytics_traffic_overview_service.py` : `try_analytics_traffic_overview_turn` | message | stop_pipeline dict | handler | intent None → skip |
| 18 | Resource (again) | E1 | `connector_resource_resolver.py` : `resolve_resource` | GA4 | ResourceResolution | connector config | ambiguous → clarify |
| 19 | GA4 execute | Adapter | `google_analytics.py` : `run_ga4_report` | property_id | report JSON | **30d rolling, not calendar month** | API error → blocked |
| 20 | State patch | Continuity | `store_active_analysis` | result | active_analysis | task_state | — |
| 21 | Compose | Output | `response_composer.py` : `compose_reply_events` | kind=canned | SSE text | composer | — |
| 22 | Persist | Trace | cognitive loop OBSERVE/LEARN | outcome | audit_events | DB | — |

### Observed failure path (matches production report)

| Turn | User | What happens | Root cause |
|------|------|--------------|------------|
| 1 | "Tell me what my website traffic was last month." | May not enter analytics handler if **GA not connected** (`detect_analytics_traffic_intent` → `None`); falls to ReAct/RAG/generic | Intent handler **requires connected GA**; no honest capability-first "connect analytics" short path on all forks |
| 1 | (same, no connector) | "does not know what/where to search" | `run_resource=false` when `connected=∅`; web_search/RAG may activate incorrectly |
| 2 | "Look at GA4." | Named connector → `run_resource=true` | Semantic resolution works |
| 2 | (property not linked) | Asks for website/property | OAuth connected ≠ property linked; multi-property OAuth leaves `pending_property` |
| 3 | Execution attempt | Parameter errors | ReAct path: `_ga_property_id` no Admin API fallback; or model-built report body invalid |

### Flow diagram (simplified)

```
HTTP → assistant_chat → execute_task_streaming
  → Intent Gateway? (usually fallthrough)
  → assess_cognitive_resolution_needs + run_cognitive_resolution (E1)
  → route_capability_for_turn + reconcile_execution_plan (E5)
  → CognitiveTurnKernel.run_pre_act
  → [analytics_short_circuit? disable unified LIVE]
  → apply_unified_turn_live? (often skipped for traffic)
  → should_run_connector_preflight? (usually false)
  → compile_assistant_turn_context (E4) + prepare_assistant_turn
  → should_clarify (E3)
  → try_analytics_traffic_overview_turn OR ReAct OR connector fallback
  → compose_reply_events → SSE complete
```

---

## 3. Routing / fork map

| Path | Trigger | ContextCompiler | ExecutionPlan | Capability route | Resource resolver | Param compile | E3 clarify | Self-repair | Response |
|------|---------|-----------------|---------------|------------------|-------------------|---------------|------------|-------------|----------|
| Intent Gateway shortcut | conf ≥ 0.92 | No | No | No | No | No | No | No | Composer canned |
| Unified LIVE | flag on, no SC bypass | `compile_unified_reasoning_context` | may stage pending | partial | **No in context** | model | LIVE clarify kinds | limited | model stream + composer |
| Analytics short-circuit | traffic intent + GA connected | Yes (before SC) | Yes (cross-source plan) | Yes | **Yes in handler** | **preset** | E3 in handler | retry in handler only | Composer canned |
| Connector preflight | pending / orchestration | Yes | Yes | Yes | partial | workflow schema | Yes | workflow gate | governed |
| ReAct classical | default fallthrough | Yes | react plan patch | narrows tools | **Phase A only; not at invoke** | **model** | should_clarify | ReAct retry | model + composer |
| Connector fallback | ReAct connector fail | Yes | reuse | mapper | partial | ledger | Yes | mapper | governed |
| Workflow canvas | stored def | No | retrieved plan | binding | per step | workflow | per step | workflow | not composer universal |
| Voice | spoken_mode=true | Same kernel | Same E5 | Same | Same | Same | Same | Same | composer + TTS |
| Intelligence Hub deterministic | IH surface + match | No | No | No | No | No | No | No | SSE shortcut |
| Intelligence Hub LLM | IH no match | Yes | Yes | Yes | Same as chat | Same | Same | Same | composer |

**Structural bug:** `"website traffic last month"` can produce **different date semantics** (rolling 30d vs model-inferred calendar month vs stub) depending on fork — **Invariant I FAIL**.

Evidence: `analytics_traffic_overview_service.py` L619–631 hard-coded dates; unified LIVE/ReAct unconstrained.

---

## 4. Business intent resolution

### Test phrases → internal representation

| User phrase | Semantic match | Capability ID | Business object | Timeframe compiled | Analysis type |
|-------------|------------------|---------------|-----------------|-------------------|---------------|
| Tell me what my website traffic was last month | `mentions_analytics_traffic_language` + regex | `analytics.traffic_overview` (if GA connected) | website (implicit) | **NOT compiled** — "last month" ignored on SC path | traffic overview |
| How did our website do last month? | `mentions_website_performance_language` | same | website | NOT compiled | performance |
| How many people visited our site? | traffic markers | same | website | NOT compiled | traffic |
| How is the website performing? | performance patterns | same + GSC caps | website | NOT compiled | cross-source if GA+GSC |
| Check our web analytics | traffic/analytics markers | `analytics.query` or traffic | analytics (vague) | NOT compiled | query vs overview fork |
| What happened to traffic? | `\btraffic\b` | traffic overview if connected | vague | NOT compiled | overview |
| Why did website traffic drop? | traffic + causal ask | capability read + may RAG | website | NOT compiled | **diagnostic — no causal handler** |

### Equivalent of `BusinessTask`?

**No single canonical type.** Distributed state:

| Field | Nearest existing | Authoritative? |
|-------|------------------|----------------|
| objective | user message + `classification.intent` | No — not structured |
| business_object | implicit in capability / regex | No |
| capability | `classification.capability_id`, `CapabilityRoute` | Partial |
| timeframe | **absent** (except `active_analysis` referent) | No |
| comparison | `reference_resolver` referent | Partial |
| desired_output | handler-specific | No |
| constraints | governance flags | Partial |

`active_analysis` in `task_state` (`conversation_state_service.py`) stores post-hoc analytics context — **not ingress canonical form**.

**Verdict:** Architecture jumps from **words → capability/connector hints → tools** without a persisted **compiled business task** object.

---

## 5. Capability-first vs connector-first finding

| Stage | Model | Evidence |
|-------|-------|----------|
| Phase A ingress | **Capability-leaning** for analytics language | `assess_cognitive_resolution_needs` → `analytics_capabilities` |
| Capability router | **Capability-first** when connected | `route_capability_for_turn` → `analytics.traffic_overview` |
| ExecutionPlan | **Capability-first steps** | `build_cross_source_analytics_plan` uses capability ids |
| Analytics handler | **Capability-first execution** | Preset GA4 report — not tool name exposed |
| ReAct path | **Connector-first** | Model sees `google_analytics_*` tool names |
| ChatActionMapper fallback | **Connector-first** | NL → `hubspot.contacts.search` |
| User failure mode | **Connector-first** | User must say "Look at GA4" to disambiguate |

**Trace conclusion:** **Hybrid, fork-dependent.** Governed/analytics-short-circuit paths are capability-first; **ReAct default is connector-first**. Production failures often occur when requests **miss the short-circuit** and land in ReAct.

---

## 6. Source discovery analysis

For `analytics.website_performance`:

| Source | Discovery mechanism | When evaluated |
|--------|---------------------|----------------|
| GA4 connected | `list_connected_integrations()` | Early in `execute_task_streaming` |
| GSC connected | same + `resolve_analytics_capabilities_for_message` | Phase A + cross-source handler |
| HubSpot | semantic registry | Not auto-included for website performance |
| Auth state | `connector_availability_service.evaluate_connector_availability` | On invoke / UI; **not always pre-plan** |
| Execution availability | matrix + availability service | Per-action when action_key set |

**Canonical service:** `connector_availability_service.py` — **partial** (HubSpot scope map only; not all vendors).

**Gap:** Connection list is known early, but **capability-eligible source set** is not passed as a compiled input to ReAct tool_choice. Model re-discovers connectors from tool list.

---

## 7. Resource-resolution analysis

See [connector-action-wiring-audit.md § H](./connector-action-wiring-audit.md#h-connector-resource-model) for adapter inventory.

### GA4 trace

```
OAuth connected → config.property_id?
  yes → resolve_ga4_property (linked_config, confidence 0.98)
  no  → Admin API list properties
    1 property → auto-select
    N properties → ambiguous → E3 clarify
    0 → not_found → blocked message
```

### API-required vs user-required failures

| Condition | Should ask user? | Actual behavior |
|-----------|----------------|-----------------|
| 1 linked property in config | **No** | Correct on SC path |
| 1 discovered property | **No** | Correct |
| N properties, no domain hint | **Yes (business labels)** | E3 message — OK |
| N properties, primary domain in org profile | **No** | **FAIL — no domain→property map** |
| OAuth ok, property pending | **No — prompt link UI** | Often asks property/website |
| ReAct invoke, config empty | **No — resolver** | **FAIL — `_ga_property_id` only** |

**Resolver before clarification:** **Yes on Phase A** and analytics handler; **No on ReAct tool invoke**.

**Persistence:** `active_analysis.property_id` after successful SC; follow-up referents work (`test_phase_a` scenario E).

---

## 8. Organization / business identity analysis

| Data | Location | Authoritative? | Used by resource resolver? | Used by ContextCompiler? |
|------|----------|----------------|---------------------------|-------------------------|
| Company name | org settings, KG nodes | partial | No | indirect |
| Primary website | **not canonical field found** | No | **No** | No |
| GA4 property link | connector `config.property_id` | Yes for GA4 | Yes | No |
| Domain → property map | **absent** | — | — | — |
| CRM tenant | connector config | Yes | HubSpot adapter | No |
| Entity bindings | `entity_resolution_store` | Yes for CRM/list | Apollo/Asana inference only | No |

**Missing link:** Company website in business graph **does not** constrain GA4 property selection — explains "my website" still triggering property questions when multiple GA4 properties exist or link pending.

---

## 9. Time-resolution analysis

| Phrase | Handler | Result |
|--------|---------|--------|
| last month | analytics SC | **Ignored** — uses 30d rolling |
| last month (follow-up) | reference_resolver | Referent to `active_analysis`; **stub response** (comparison rolling out) |
| last 30 days | analytics SC | Approx match to 30d window |
| yesterday / YTD / quarter | ReAct / model | **Model inference** — non-deterministic |

**No canonical time resolver module.** Tenant timezone not applied in analytics handler.

**Invariant violation:** User says "last month"; system answers "last 30 days" without disclosure on SC path (partial leak in prose only if composer mentions 30 days).

---

## 10. Parameter-resolution architecture

### Systems involved

| System | Role |
|--------|------|
| `parameter_ledger.py` | Write-slot binding (email, channel, …) — **not GA4** |
| `schema_param_extractor.py` | Schema-constrained fill for governed writes |
| `action_parameters.py` | ReAct JSON Schema |
| `action_workflow_schema.py` | Governed workflow required fields |
| `action_selection_gate.py` | Workflow invoke validation |
| `connector_resource_resolver.py` | property_id, site URL, etc. |
| `capability_ontology/registry.py` | capability → action binding |
| ReAct tool args | Model inference |
| analytics handler | **Hard-coded** report params |

### Canonical parameter compiler?

**No.** Arguments assembled by **path-specific ad hoc logic**.

### Why tools still invoked with missing/invalid parameters

1. ReAct bypasses `action_selection_gate`
2. JSON Schema ≠ workflow schema ≠ executor guards ([connector-action-wiring-audit § C](./connector-action-wiring-audit.md))
3. Resource resolver not called at `invoke_tool` for GA4
4. No ParameterSourceRule registry

---

## 11. Parameter-error forensic analysis

| Root cause class | Examples | Evidence |
|------------------|----------|----------|
| RESOURCE_NOT_RESOLVED | GA4 property missing on ReAct | `tool_service._ga_property_id` |
| TIME_NOT_RESOLVED | "last month" → wrong window | analytics handler dates |
| CAPABILITY_RECIPE_INCOMPLETE | traffic overview lacks date recipe | handler hard-code |
| SCHEMA_DRIFT | HubSpot search filter_groups | `hubspot-search-validation-dead-end.md` |
| TOOL_SELECTION_WRONG | deals.search vs deals.list | probe JSON |
| LLM_ARGUMENT_HALLUCINATION | invalid GA4 dimensions | ReAct path |
| DEFAULT_MISSING | empty required in inferred schema | catalog_http |
| STATE_LOST | follow-up not using active_analysis | ReAct new intent |
| CONNECTOR_METADATA_STALE | pending_property treated as connected | OAuth status |
| VALIDATION_TOO_LATE | executor rejects after invoke | HubSpot class |
| HANDLER_BYPASS | SC vs ReAct different validation | routing fork |

---

## 12. Preflight validation analysis

**Desired pipeline not present as single gate.**

| Step | Governed | Analytics SC | ReAct |
|------|----------|--------------|-------|
| resolve resource | partial | Yes | Phase A only |
| resolve parameters | workflow schema | preset | model |
| schema validation | action_selection_gate | none | JSON Schema (weak) |
| permission/scopes | availability on invoke | session check | on invoke |
| provider constraints | executor | executor | executor |

**Pattern:** `tool call → provider error → ask user` on ReAct; `compile → validate → execute` on workflow invoke only.

---

## 13. Clarification analysis (E3)

E3 policy (`clarification_policy.py`): **"discover before ask"** — implemented for resource resolution outcomes.

| Clarification | Avoidable? | Classification |
|---------------|------------|----------------|
| Which GA4 property (3 plausible business sites) | No | **NECESSARY** |
| Which GA4 property (1 matches org domain) | **Yes** | **AVOIDABLE** — no domain map |
| Provide property ID | **Yes** | **AVOIDABLE** — API id leak |
| Which connector | Often yes | **AVOIDABLE** — capability routing |
| Required parameters after failed tool | Often yes | **AVOIDABLE** — preflight |

**E3 bypass:** `clarification_engine` skips clarify when `resolution_trace.clarification_required=false` and resource resolved — **good**. Does not prevent `should_clarify` under-specified rules or model-driven clarify on ReAct path.

### State matrix (expected vs actual)

| State | Expected | Actual (typical) |
|-------|----------|------------------|
| A: 1 GA4 + 1 GSC | Zero clarify, auto resource | **PASS on SC path** (test scenario A) |
| B: 3 GA4, 1 matches domain | Zero clarify | **FAIL** — ambiguous without domain map |
| C: 3 genuine sites | One concise clarify | **PASS** (E3 messages) |
| D: expired OAuth | Auth message | **PARTIAL** — SC path OK; ReAct may differ |
| E: no connector | Connect path | **PARTIAL** — may web-search instead |
| F: recoverable param error | Self-repair | **FAIL** on ReAct |

---

## 14. Task continuity analysis

Canonical state keys (`cognitive_harness_behavior.py`):

- `execution_plan` (E5)
- `pending_task` / `PendingAction` (transitional)
- `active_analysis`
- `previous_option_set`
- `offered_action`
- `resolution_trace`
- `connector_session.activeEntities`

| Follow-up | Expected | Actual |
|-----------|----------|--------|
| "Use GA4" | Update same task resource target | Phase A named connector → resource run |
| "gravitre.app" | Domain hint → property select | **No domain→property wiring** |
| "All of them" | option_set select_all | **PASS** (reference_resolver scenario D) |

**Risk:** ReAct may treat follow-up as **new intent** if `detect_analytics_traffic_intent` returns None.

---

## 15. Error recovery / self-repair

| Error | Parse | Classify | Repair | Retry | Replan | User ask |
|-------|-------|----------|--------|-------|--------|----------|
| missing resource | partial | partial | No | No | No | Yes |
| invalid parameter | yes | validation_error | No | ReAct loop | limited replanner | Yes |
| unsupported metric | partial | validation_error | No | No | No | Yes |
| expired token | yes | auth_expired | reconnect msg | No | No | Yes |
| rate limit | yes | rate_limited | backoff | yes (invoke) | No | sometimes |
| schema mismatch | yes | validation_error | **No** | No | No | Yes |
| empty result | partial | none | No | No | No | model prose |

`cognitive_execution_replanner.py` — cross-source plan builder, **not** argument repair.

`action_availability_honesty.py` — response rewrite only.

---

## 16. Retry / replan behavior

- `invoke_tool`: max 2 retries transport (`tool_service.py`)
- ReAct: model re-attempt loop (`react_engine.py`)
- ExecutionPlan: `reconcile_execution_plan` continues in-flight plan on confirm
- No global cap on clarification/repair loops documented — **regression risk**

---

## 17. Retrieval / search gating

Priority for operational analytics:

1. `should_suppress_knowledge_base_for_turn` — prefers connector when analytics intent detectable
2. `assess_cognitive_resolution_needs` — analytics_short_circuit flag
3. `context_registry` — chitchat suppresses RAG
4. `should_short_circuit_before_generation` — external Q handling

**Gap:** When analytics handler **misses** (GA not connected), **web_search/RAG may activate** for URL-like or general questions — prior "business URL triggered web research" class.

**Invariant H:** **PARTIAL** — suppressed on SC path only.

---

## 18. Multi-source synthesis

`_try_cross_source_website_overview_turn` + `build_cross_source_analytics_plan`:

- Triggers when GA4 **and** GSC connected + website performance language
- Parallel ExecutionPlan reads
- **Does not require user to name both**

**Gap:** `analytics.traffic_overview` capability binds GA4 only in ontology — GSC is handler special-case, not capability recipe.

---

## 19. Response abstraction analysis

Response Composer (`response_composer.py`) — sole prose path for canned/clarify/error.

| Leak type | Example | Source |
|-----------|---------|--------|
| Property ID request | "provide property ID" | model ReAct / tool error |
| Parameter vocabulary | "filter_groups" | HubSpot validation_error |
| Connector name | "google_analytics not connected" | format messages (improved) |
| Good pattern | "link your property in Connectors" | analytics handler L585–588 |

Composer receives `workflow_status` but **not** structured repair hints — limits business-operator tone.

---

## 20. Manus-like behavioral gap matrix

| Characteristic | Rating | Component |
|----------------|--------|-----------|
| goal-first interaction | PARTIAL | capability router; ReAct tool-first |
| autonomous task decomposition | PARTIAL | orchestration + E5 plan |
| capability selection | PARTIAL | 9 capabilities; analytics SC |
| tool discovery | PRESENT | execution matrix |
| resource discovery | PARTIAL | 9/85 connectors |
| parameter completion | BYPASSED | ReAct path |
| environment awareness | PARTIAL | connected list; not action-level |
| persistent task state | PRESENT | E5 ExecutionPlan |
| multi-step execution | PRESENT | orchestration |
| self-repair | ABSENT | no argument repair |
| retry | PARTIAL | transport only |
| replanning | PARTIAL | replanner limited |
| multi-source synthesis | PARTIAL | cross-source analytics |
| tool-result grounding | PRESENT | SC + audit |
| minimal clarification | INCONSISTENT | E3 vs ReAct |
| progress without premature completion | PRESENT | SSE stages |
| terminal-state guarantees | PARTIAL | terminal_turn_policy |
| business-level final answer | PARTIAL | SC good; ReAct variable |
| cross-tool execution | PRESENT | orchestration |
| governed write actions | PRESENT | write gate |
| persistent business memory | PARTIAL | KG exists; not wired to params |

---

## 21. Cross-department scenario results (architecture trace)

| Dept | Example ask | Capability | Source | Resource | Params | Plan | Clarify? | Execute? |
|------|---------------|------------|--------|----------|--------|------|----------|----------|
| Sales | Deals at risk? | none canonical | HubSpot/SF | portal/org | deal stage filters | ReAct/plan | likely | PARTIAL |
| Marketing | Campaign performance | none | GA4/ads/meta | property/account | date range | ReAct | yes (dates) | PARTIAL |
| Finance | Unpaid customers | none | Stripe/QB | company | status filter | ReAct | likely | PARTIAL |
| Support | Customer complaints | none | Zendesk/Intercom | workspace | sentiment q | RAG+ReAct | varies | PARTIAL |
| HR | Interviewing this week | none | Greenhouse/Workday | tenant | calendar | ReAct | likely | MINIMAL |
| IT | Systems need attention | none | PagerDuty/GitHub | org | health q | signals+RAG | varies | PARTIAL |
| Cyber | Critical vulnerabilities | none | NVD/CISA KEV | platform | CVE filters | gravitre_managed | low | READ ok |
| Executive | What changed this week | none | multi | multi | timeframe | synthesis | yes | PARTIAL |
| Comms | Email John proposal | email.send | Gmail | mailbox | to, subject, body | governed write | ledger | PRESENT |

**Pattern:** Department asks **without canonical capabilities** → **ReAct connector-first** → parameter/clarify failures recur.

---

## 22. Source-of-truth ownership matrix

| Concept | Canonical owner | Duplicate owners | Consumers |
|---------|-----------------|------------------|-----------|
| business intent | **none** | classification, gateway | router, composer |
| active task | `task_state.execution_plan` (E5) | pending_task, react plan | dispatch, UI |
| company identity | org settings / KG | marketing packs | weak |
| connector state | DB + availability service | health_monitor | UI, invoke |
| resource identity | connector config + resolver | conversation_context hint | invoke, SC |
| capability | capability_ontology/registry | department recipes | router, E5 |
| tool schema | action_parameters + workflow | executor guards | ReAct, gate |
| parameter state | parameter_ledger | clarified_params legacy | governed writes |
| ExecutionPlan | execution_plan_service | pending_task projection | E5 dispatch |
| observation | audit_events | tool result dict | trace, composer |
| error state | ToolError codes | workflow_status | composer |
| memory | KG + memory services | conversation history | orchestrator |

**Ambiguity hotspots:** pending_task vs ExecutionPlan (E5 converging), classification vs capability_id, resolution_trace vs active_analysis.

---

## 23. Sequencing analysis

### Target vs actual

| Target stage | Exists as | Order issue |
|--------------|-----------|-------------|
| UNDERSTAND | Phase A semantic | OK early |
| RESOLVE TASK | **missing canonical object** | skipped |
| COMPILE CONTEXT | E4 ContextCompiler | **before** execution but **without** resolution payload |
| SELECT CAPABILITY | capability_router | OK before LIVE/ReAct |
| DISCOVER SOURCES | connected list | OK but not fed to ReAct compactly |
| RESOLVE RESOURCE | Phase A + handler | **duplicated**; not at invoke |
| RESOLVE PARAMETERS | **missing compiler** | after tool selection on ReAct |
| PREFLIGHT | action_selection_gate | **after** tool choice; workflow only |
| PLAN | E5 reconcile | OK |
| EXECUTE | invoke_tool / handlers | OK |
| OBSERVE | audit + loop | OK |
| REPAIR/REPLAN | limited | **too late** |
| SYNTHESIZE | composer / model | OK |
| RESPOND | composer | OK |
| LEARN | loop LEARN | OK |

**Core sequencing bug:** **Tool selection before parameter compilation** on ReAct path.

---

## 24. Special-case inventory (Part 23)

| Case | Location | Class |
|------|----------|-------|
| Analytics traffic short-circuit | `analytics_traffic_overview_service.py` | **ARCHITECTURAL_LEAK** — masks missing generic capability compiler |
| LIVE disabled for analytics SC | `agent_intelligence.py` ~3157 | LEGITIMATE dual-path guard |
| GA4 `resolve_ga4_property` special | `connector_resource_resolver.py` | LEGITIMATE adapter |
| HubSpot scope map | `connector_availability_service.py` | LEGITIMATE |
| HubSpot search filter resolver | post-fix shared resolver | LEGITIMATE |
| Cross-source GA4+GSC | `cognitive_execution_replanner.py` | LEGITIMATE recipe |
| Slack channel hints | chat_action_mapper | TEMPORARY_COMPATIBILITY |
| `_ga_property_id` in tool_service | tool_service | **ARCHITECTURAL_LEAK** — bypasses resolver |
| 30d hard-coded dates | analytics handler | **ARCHITECTURAL_LEAK** — should be time resolver |
| Keyword routing regexes | analytics_traffic_overview_service | TEMPORARY_COMPATIBILITY |

**No new GA4 prompt hacks recommended.**

---

## 25. Regression-risk map (for future fixes)

| Area | Risk if changing param compile / preflight |
|------|---------------------------------------------|
| E1 semantic aliases | Low — extend, don't replace |
| E2 tracing | Low — add fields |
| E3 clarification | Medium — fewer false clarifies; test matrix |
| E4 ContextCompiler | Medium — add resolution slice |
| E5 ExecutionPlan | Medium — plan steps need compiled params |
| ReAct | **High** — tool call behavior changes |
| Voice | High — shared kernel |
| Workflow | Medium — gate already strict |
| Write governance | **Critical** — must not auto-fill writes without approval |
| Tenant isolation | **Critical** — resource auto-select must respect org |
| Streaming/SSE | Low |
| Latency | Medium — preflight adds ms |

---

## 26. Latency map (audit only)

| Stage | Typical cost | Cacheable? |
|-------|--------------|------------|
| Intent gateway | ms | yes (phrase bank) |
| Phase A resolution | 50–500ms if Admin API | property list cache |
| ContextCompiler / RAG | 200ms–2s | retrieval cache |
| Unified LIVE | 1–5s | — |
| ReAct loop | 2–15s | — |
| GA4 report | 200–800ms | short TTL |
| Composer | 0–2s | canned=0 |

**Parallelizable:** resource discovery + RAG prefetch; cross-source GA4+GSC already PARALLEL in E5.

---

## 27. Security / governance analysis

Auto-resolve resource **acceptable** when:

- connector row scoped to org_id ✓
- OAuth token valid ✓
- action is READ ✓
- user has agent tool permission ✓

**Risk:** auto-select wrong property in multi-tenant ambiguous case → **data scope error** — domain map must respect tenant isolation.

Write parameters must **never** silent-auto-fill from model inference without ledger/approval — governed path enforces; ReAct write gate enforces approval staging.

---

## 28. Root-cause tree

```
SYMPTOM: User must supply connector/resource/parameters for ordinary business tasks
├─ CAUSE: ReAct path selects tools before params compiled
│  ├─ SUB: no invoke-time resource resolver
│  └─ SUB: action_selection_gate not on ReAct
├─ CAUSE: Analytics handler not reached
│  ├─ SUB: requires GA connected at intent detect
│  └─ SUB: unified LIVE would swallow (guard disables — OK)
├─ CAUSE: Property clarification despite "my website"
│  ├─ SUB: no domain→property map (business graph gap)
│  ├─ SUB: OAuth multi-property → pending_property
│  └─ SUB: Phase A clarification not blocking ReAct early
├─ CAUSE: Parameter errors after execution
│  ├─ SUB: schema drift (HubSpot class)
│  └─ SUB: model-hallucinated GA4 report body
├─ CAUSE: "last month" wrong period
│  └─ SUB: no time resolver; 30d hard-code
└─ CAUSE: User sees "don't know where to search"
   ├─ SUB: no analytics connected → intent None → generic path
   └─ SUB: web_search/RAG competes with connect guidance
```

---

## 29. P0 / P1 / P2 / P3 findings

### P0 — blocks autonomous execution

| ID | Finding | Component |
|----|---------|-----------|
| P0-1 | ReAct invokes connector tools without resource/parameter preflight | react_engine + tool_service |
| P0-2 | Equivalent request, different semantics across forks | routing stack |
| P0-3 | API IDs exposed as user clarifications on ReAct path | clarification + tool errors |

### P1 — repeated failure / avoidable clarify

| ID | Finding | Component |
|----|---------|-----------|
| P1-1 | No time resolver — "last month" mishandled | analytics handler |
| P1-2 | Phase A clarification not enforced before model turn | agent_intelligence |
| P1-3 | Business domain → GA4 property mapping absent | org graph + resolver |
| P1-4 | Schema drift class (HubSpot fixed; inferred actions remain) | action catalog |
| P1-5 | Intent handler skips when GA not connected — weak connect guidance | analytics_traffic_overview_service |

### P2 — quality / reliability

| P2-1 | ContextCompiler omits resolution_trace | context_compiler |
| P2-2 | 248 implemented_unverified actions | catalog |
| P2-3 | Capability ontology thin (9 vs 732 actions) | capability_ontology |
| P2-4 | GSC not in capability.traffic_overview binding | registry |

### P3 — optimization

| P3-1 | Duplicate resource resolution (Phase A + handler) | pipeline |
| P3-2 | Property list API latency | cache |

---

## 30. Proposed architecture options (DO NOT IMPLEMENT)

### Option A — **Parameter compilation gate (extend `action_selection_gate`)** ⭐ preferred

| | |
|-|-|
| Problem | Tools invoked with missing params |
| Reuse | action_selection_gate, resource resolver, workflow validation |
| Modify | react_engine pre-tool hook; invoke_tool entry |
| New abstraction | `CompiledActionArgs` dataclass (optional thin) |
| Migration | Read actions first; writes unchanged governance |
| Tests | Phase A benchmark + ReAct integration |
| Risk | Medium-High |
| Behavior | Same ask → same compiled args on all paths |

### Option B — **Extend E5 ExecutionPlan with compiled step params**

| | |
|-|-|
| Problem | Plan exists but steps lack pre-resolved params |
| Reuse | execution_plan_service, cognitive_execution_engine |
| Modify | Plan reconciliation inserts resource+time+args before ACT |
| Risk | Medium |

### Option C — **Extend ContextCompiler with resolution slice**

| | |
|-|-|
| Problem | Model doesn't see resolved property/time |
| Reuse | context_compiler, resolution_trace |
| Modify | Add `compiled_task_context` to CompiledTurnContext |
| Risk | Low-Medium; doesn't alone fix invoke bypass |

### Option D — **Thin Business Task Orchestration layer**

Only if A+B insufficient — **single read-only dataclass** persisted in `task_state.compiled_task` populated by Phase A+E5, consumed by all dispatchers. **Not a new runtime.**

### Not recommended

- New parallel planner
- GA4-specific prompts
- URL-specific routing hacks
- Replacing E1–E5

---

## 31. Business Task Resolution recommendation

**REUSE + EXTEND + THIN CONTRACT**

Existing primitives suffice:

- Phase A → resource + clarification
- capability_router → capability
- execution_plan_service → plan
- reference_resolver → timeframe referents
- parameter_ledger → user-provided slots

**Missing:** canonical **`compiled_task`** projection (read-only) assembled once per turn:

```
compiled_task {
  objective_text
  capability_id
  timeframe_resolved | null
  sources[{connector, resource_id, display_name}]
  action_keys[]
  compiled_parameters{}
  clarification_decision
  preflight_status
}
```

**Do NOT** create a competing BusinessTask orchestration subsystem — **thin projection + gate**.

---

## 32. Invariant assessment A–J

| Inv | Statement | Status |
|-----|-----------|--------|
| A | User expresses goal; system resolves implementation | **PARTIAL** |
| B | Derivable params not asked | **FAIL** on ReAct |
| C | Clarification last resort | **PARTIAL** — E3 yes; engine/ReAct no |
| D | API required ≠ user required | **FAIL** |
| E | No tool without preflight | **FAIL** |
| F | Recoverable errors → repair first | **FAIL** |
| G | External action on ExecutionPlan step | **PARTIAL** — ReAct side-steps |
| H | Internal sources before web | **PARTIAL** |
| I | Same semantics all paths | **FAIL** |
| J | No implementation vocabulary | **PARTIAL** |

---

## 33. Proposed golden benchmark

Anchor: `"Tell me what my website traffic was last month."`

| Scenario | Config | Expected |
|----------|--------|----------|
| A | 1 GA4 + 1 GSC linked | 0 clarify; correct month bounds; business answer |
| B | 3 GA4, 1 matches primary domain | 0 clarify; auto-select matching property |
| C | 3 plausible business sites | 1 concise clarify with display names |
| D | GA4 auth expired | Auth message; no property ask |
| E | No analytics | Connect guidance; no web search detour |
| F | Recoverable GA4 param error | Self-repair + retry |
| G | GA4 + GSC | Multi-source without naming sources |

**Implementation location (future):** extend `test_phase_a_cognitive_runtime_benchmark.py` + live battery scripts.

**Department families:** mirror pattern for CRM read, finance AR, support ticket sentiment — capability + resource + time + preflight assertions.

---

## 34. Recommended migration sequence

1. **Read-only preflight gate** on ReAct + invoke_tool (resource + read schema) — no write behavior change  
2. **Time resolver module** — deterministic NL → date range; analytics handler consumes  
3. **Domain→property binding** — org profile + resolver; tenant-safe  
4. **compiled_task projection** in task_state — E2 trace visibility  
5. **ContextCompiler** includes compiled_task slice  
6. **Expand capability recipes** — traffic = GA4 + optional GSC  
7. **Schema convergence** — single canonical schema per action (see connector-action-wiring audit)  
8. **Golden benchmark CI** — Phase A + live smoke  

---

## 35. Files / components likely affected (future)

- `backend/app/services/action_selection_gate.py`
- `backend/app/services/react_engine.py`
- `backend/app/operators/agent_intelligence.py`
- `backend/app/services/context_compiler.py`
- `backend/app/services/execution_plan_service.py`
- `backend/app/services/analytics_traffic_overview_service.py`
- `backend/app/services/connector_resource_resolver.py`
- `backend/app/services/tool_service.py` (invoke entry)
- `backend/tests/services/test_phase_a_cognitive_runtime_benchmark.py`

---

## 36. Files / components that should NOT be touched

- G8 / Intelligence UI (`apps/web/app/intelligence/**`, hub tabs shell)
- E1–E5 **replacement** — extend only
- `cognitive_loop_controller.py` stage semantics (unless trace fields only)
- Write governance core (`catalog_write_authority`, `react_write_gate`)
- Voice transport layer (Pipecat/legacy) — behavior via shared kernel only
- New GA4/URL prompt hacks in system prompts

---

## 37. Architecture elements to preserve

- Phase A canonical resolution + resolution_trace (E1)
- E3 clarification_policy semantics
- E4 ContextCompiler single compile
- E5 ExecutionPlan as plan SoT
- Analytics traffic short-circuit (extend, don't delete)
- Response Composer as sole prose authority
- STA-303 error taxonomy
- Connector execution matrix + tool registry
- Parameter ledger for **writes**
- Cross-source analytics ExecutionPlan pattern

---

## 38. Unknowns requiring production evidence

| Unknown | Evidence needed |
|---------|-----------------|
| Frequency of ReAct vs SC for traffic asks | `audit_events` action histogram by path |
| LIVE fallthrough rate for analytics language | `unified_turn.live.fallthrough` logs |
| Multi-property GA4 tenant prevalence | connector config query |
| "Don't know where to search" exact path | conversation_id trace with routing.stages |
| Parameter error rate post HubSpot fix | STA-303 audit refresh |
| Calendar "last month" user expectation vs 30d acceptance | product sign-off |

**NOT RUN:** Live prod re-run of anchor scenario after this audit — classify recommendations as **design-level** until benchmark implemented.

---

## Audit complete

**AUDIT COMPLETE: YES** (architecture/root-cause only; no fixes implemented)

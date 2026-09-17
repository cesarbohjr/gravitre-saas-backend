# Connector Action Wiring & Capability Completeness Audit

**Part of:** [Platform Autonomous Execution Review](./platform-autonomous-execution-review.md)  
**Status:** AUDIT ONLY — no connector fixes implemented in this pass  
**Date:** 2026-09-17  
**Evidence baseline:** `connector-catalog-audit-latest.json` (regenerated 2026-09-17), code inspection, live probes cited inline

---

## Architecture overview

Gravitre separates **declaration** (catalog), **registration** (invoke_tool registry), **exposure** (execution matrix + dynamic chat tools), and **governance** (write authority + availability).

```
vendor_definitions.py (ActionSpec)
    → action_catalog/registry.py
    → connector_execution_matrix.py  ← auto-detects implemented via list_registered_actions()
    → chat_tool_bridge.py → tool_registry (AgentToolSpec)
    → ReAct / ChatConnectorExecutionService → invoke_tool

Parallel paths:
  capability_ontology/registry.py (9 capabilities) → resolver.py → tool_bridge
  parameter_ledger.py + schema_param_extractor.py → governed writes
  connector_resource_resolver.py + connector_resource_adapters.py (8 vendors + GA4)
  connector_availability_service.py → per-action scope + registration
  action_selection_gate.py → workflow invoke schema gate (not ReAct JSON Schema)
```

**Key files:**

| Concern | Path |
|---------|------|
| Catalog | `backend/app/connectors/action_catalog/` |
| Executors | `backend/app/services/tool_service.py`, `priority_connector_tools.py`, `catalog_http/` |
| Matrix | `backend/app/services/connector_execution_matrix.py` |
| Capabilities | `backend/app/capability_ontology/` |
| Parameters | `backend/app/services/parameter_ledger.py`, `action_parameters.py`, `action_workflow_schema.py` |
| Availability | `backend/app/connectors/connector_availability_service.py` |
| Docs | `backend/docs/connector-chat-execution.md`, `docs/engineering/connector-action-schema-standard.md` |

---

## A. Connector → Capability → Action Map

### Full matrix

The complete 732-action matrix is in:

- **JSON:** `docs/delivery/connector-catalog-audit-latest.json` (fields: `vendor`, `action_id`, `implementationStatus`, `testStatus`, `verificationClaim`, `approvalRequired`, …)
- **CSV:** `docs/delivery/connector-catalog-audit-latest.csv`
- **API:** `GET /api/connectors/catalog/execution-matrix`

Below: **representative business-relevant slices** for priority connectors. Capability IDs come from `capability_ontology/registry.py` where mapped; otherwise inferred business capability from action id.

### Google Analytics (GA4)

| Connector | Provider | Capability | Action ID | R/W | API operation | Impl | Reg | Enabled | Schema | Resource resolver | Tests | Prod verified |
|-----------|----------|------------|-----------|-----|---------------|------|-----|---------|--------|-------------------|-------|---------------|
| google_analytics | Google | analytics.query | google_analytics.reports.run | READ | runReport | Y | Y | Y | inferred | GA4 property (`resolve_ga4_property`) | live | Y |
| google_analytics | Google | analytics.traffic_overview | google_analytics.reports.run | READ | runReport (preset dims) | Y | Y | Y | inferred | GA4 property | live | Y |
| google_analytics | Google | — | google_analytics.realtime.run | READ | runRealtimeReport | Y | Y | Y | inferred | GA4 property | live | Y |
| google_analytics | Google | — | google_analytics.properties.list | READ | admin.properties.list | Y | Y | Y | inferred | connection | live | Y |
| google_analytics | Google | — | google_analytics.metadata.list | READ | metadata.get | Y | Y | Y | inferred | GA4 property | live | Y |
| google_analytics | Google | — | google_analytics.reports.batch | READ | batchRunReports | Y | Y | Y | inferred | GA4 property | live | Y |
| google_analytics | Google | — | google_analytics.audiences.create | WRITE | audiences.create | Y | Y | approval | inferred | GA4 property | live | Y |
| google_analytics | Google | — | google_analytics.conversions.create | WRITE | conversionEvents.create | Y | Y | approval | inferred | GA4 property | live | Y |

**Registry alias:** catalog `google_analytics.*` → registry `analytics.*` (`tool_aliases.py`).

**Business completeness vs GA4 API:** **PARTIAL** — covers traffic, realtime, metadata, batch; does not expose dedicated actions for geography/device/campaign comparison as first-class capabilities (model must compose `reports.run` with dimensions/metrics). Provider dimension/metric incompatibility rules **not structurally encoded**.

### Google Search Console (GSC)

| Connector | Provider | Capability | Action ID | R/W | API operation | Impl | Reg | Enabled | Schema | Resource resolver | Tests | Prod verified |
|-----------|----------|------------|-----------|-----|---------------|------|-----|---------|--------|-------------------|-------|---------------|
| google_search_console | Google | — (no capability binding) | google_search_console.searchAnalytics.query | READ | searchanalytics.query | Y | Y | Y | inferred | site URL (`resolve_gsc_site`) | live | Y |
| google_search_console | Google | — | google_search_console.sites.list | READ | sites.list | Y | Y | Y | inferred | connection | live | Y |
| google_search_console | Google | — | google_search_console.sites.get | READ | sites.get | Y | Y | Y | inferred | site URL | live | Y |
| google_search_console | Google | — | google_search_console.sitemaps.list | READ | sitemaps.list | Y | Y | Y | inferred | site URL | live | Y |

**Registry alias:** `google_search_console.*` → `searchconsole.*`.

**Business completeness:** **PARTIAL** — query + site management; no dedicated query/page/performance capability IDs; not wired into `analytics.traffic_overview` despite common joint "website performance" asks.

### HubSpot

| Connector | Provider | Capability | Action ID | R/W | API operation | Impl | Reg | Enabled | Schema | Resource resolver | Tests | Prod verified |
|-----------|----------|------------|-----------|-----|---------------|------|-----|---------|--------|-------------------|-------|---------------|
| hubspot | HubSpot | crm.contact.read | hubspot.contacts.get | READ | CRM v3 GET contact | Y | Y | Y | override | portal | live | Y |
| hubspot | HubSpot | crm.contact.read | hubspot.contacts.search | READ | CRM v3 search | Y | Y | Y | override ⚠ | portal | live | Y (schema fixed 2026-09) |
| hubspot | HubSpot | crm.contact.read | hubspot.contacts.list | READ | CRM v3 list | Y | Y | Y | override | portal | live | Y |
| hubspot | HubSpot | crm.contact.create | hubspot.contacts.create | WRITE | CRM v3 POST | Y | Y | approval | override | portal | live | Y |
| hubspot | HubSpot | crm.contact.update | hubspot.contacts.update | WRITE | CRM v3 PATCH | Y | Y | approval | override | portal | live | Y |
| hubspot | HubSpot | — | hubspot.deals.search | READ | CRM v3 search | Y | Y | Y | override ⚠ | portal | live | Y |
| hubspot | HubSpot | — | hubspot.deals.list | READ | CRM v3 list | Y | Y | Y | override | portal | live | Y |
| hubspot | HubSpot | — | hubspot.deals.create/update | WRITE | CRM v3 | Y | Y | approval | override | portal | live | Y |
| hubspot | HubSpot | — | hubspot.lists.* / sequences / tickets / companies | MIXED | CRM v3/v4 | Y | Y | mixed | override | portal | live | Y |

**Business completeness:** **FULL** for common CRM ops (contacts, deals, lists, tickets). **Risk:** search vs list tool-selection still exposes schema/executor edge cases on sibling actions (see § B, T).

### Slack

| Connector | Provider | Capability | Action ID | R/W | API operation | Impl | Reg | Enabled | Schema | Resource resolver | Tests | Prod verified |
|-----------|----------|------------|-----------|-----|---------------|------|-----|---------|--------|-------------------|-------|---------------|
| slack | Slack | messaging.channel.post | slack.post_message | WRITE / EXT_COMM | chat.postMessage | Y | Y | approval | override | workspace | live | Y |
| slack | Slack | — | slack.conversations.list | READ | conversations.list | Y | Y | Y | override | workspace | live | Y |
| slack | Slack | — | slack.conversations.history | READ | conversations.history | Y | Y | Y | override | workspace + channel | live | Y |
| slack | Slack | — | slack.users.list | READ | users.list | Y | Y | Y | override | workspace | live | Y |
| slack | Slack | — | slack.files.upload | WRITE | files.upload | Y | Y | approval | override | workspace | live | Y |

**Governance:** `slack.post_message` = EXTERNAL_COMMUNICATION + write approval (`catalog_write_authority.py`).

### Salesforce (abbreviated)

14 actions — leads/accounts/opportunities/tasks CRUD + search. **FULL** for core CRM. Capability bindings: `crm.contact.create` → `salesforce.leads.create`, `crm.contact.search` → `salesforce.leads.search`. Resource: org/instance URL.

### Platform totals (85 connectors)

See **Section S** health matrix. Priority tier-1 connectors (HubSpot, Slack, GA4, GSC, Salesforce, Gmail) are **implemented + tested**. Weakest coverage: vendors with 100% `no_tests` (Confluence 12/12, Twilio 10/10, Hootsuite 8/8, …).

---

## B. Ghost Actions

| Category | Count | Examples | Risk |
|----------|------:|----------|------|
| **REGISTERED_BUT_NOT_IMPLEMENTED** | 2 | `webhook.connectors.get`, `webhook.post.replay` | Low — webhook vendor edge |
| **IMPLEMENTED_BUT_NOT_REGISTERED** | ~56 keys | `analytics.*`, `drive.*`, `searchconsole.*` (registry short names) | **False alarm** — intentional aliases via `tool_aliases.py`, not ghosts |
| **REGISTERED_WITH_WRONG_SCHEMA** | class-level | All 4 HubSpot `*.search` (fixed live 2026-09); risk remains on inferred-schema actions | **High** |
| **CONNECTED_BUT_UNAVAILABLE** | per-org | Partial HubSpot OAuth scopes; GA4 `pending_property`; GSC `pending_site` | **High** — surfaces as param/validation confusion |
| **PARTIALLY_IMPLEMENTED** | unknown set | `catalog_http` auto-stubs for catalog gaps | **Medium** — may accept params executor ignores |
| **READ_ONLY_BUT_ADVERTISED_AS_WRITE** | 0 found | — | — |
| **WRITE_CAPABLE_BUT_NOT_GOVERNED** | 0 catalog violations | write authority enforced | — |
| **CAPABILITY_MAPPED_TO_WRONG_ACTION** | 0 proven | `analytics.traffic_overview` → `reports.run` is intentional | — |
| **ACTION_EXISTS_BUT_RESOURCE_RESOLUTION_MISSING** | ~723 actions | Any vendor outside 8 adapters + GA4 | **High** for multi-property tenants |

**Alias trap:** Raw lookup of `google_analytics.reports.run` without alias resolution appears unimplemented; always use `catalog_tool_is_implemented()` / `resolve_registry_action()`.

---

## C. Action Schema Validity

### Layers (four + CI)

| Layer | File | Validates |
|-------|------|-----------|
| LLM tool JSON Schema | `action_parameters.py`, `schema_generator.py` | ReAct tool definitions |
| Chat workflow schema | `action_workflow_schema.py` | Governed write clarification |
| Call-time gate | `action_selection_gate.py`, `action_workflow_validation.py` | Workflow `invoke_tool` |
| Executor guards | `tool_service.py`, vendor clients | Imperative `ToolValidationError` |
| CI lint | `test_action_schema_standard_lint.py` | Catalog quality metadata |

**There is no runtime JSON Schema validator** (no `jsonschema` on args). ReAct can call tools with args that pass JSON Schema but fail executor guards, or vice versa.

### Documented cross-layer disagreement (exemplar)

**HubSpot search actions** — see `docs/delivery/hubspot-search-validation-dead-end.md`:

| Layer | Contract | Reality |
|-------|----------|---------|
| `action_parameters` JSON Schema | `required: []`, optional `query` | Model sends query-only |
| Executor | Required non-empty `filter_groups`; ignored `query` | 100% validation_error on criteria-less calls |
| Workflow schema | May differ again | Chat gate uses workflow fields |

**Live evidence:** `hubspot-deals-search-validation-probe.json` — 4/4 failures on `hubspot.deals.search`, 8/8 success on `hubspot.deals.list` for identical user intent class.

### GA4 / GSC schema notes

- GA4/GSC actions use **inferred schemas** from action id patterns — no hand-tuned overrides in `ACTION_PARAMETERS`.
- Date formats, pagination, dimension/metric enums rely on executor + model inference.
- `api_reference_map.json` documents endpoints but is reference-only (drift detection), not runtime validation.

### Schema disagreement pattern (general)

| Symptom | Typical cause |
|---------|---------------|
| "Invalid parameters" on read | Executor stricter than JSON Schema |
| Clarification loop on write | Workflow schema marks required; JSON Schema optional |
| ReAct succeeds, workflow fails | Different gates on same action |
| Transport error → validation_error | Reduced by STA-303 + `_classify_error` transport hints |

---

## D. Action Parameter Source Map

**No enum types** (`USER_EXPLICIT`, `RESOURCE_RESOLVER`, …) exist in code. Equivalent mechanisms:

| Audit class | Implementation | Location |
|-------------|----------------|----------|
| USER_EXPLICIT | `user_message`, `unified_turn_live` | `parameter_ledger.py` `_SLOT_SOURCE_RANK` |
| TASK_CONTEXT | `staged_plan`, `awaiting_params_resume` | parameter ledger |
| BUSINESS_GRAPH | inference source `"org entity cache"` | `connector_parameter_inference.py` |
| RESOURCE_RESOLVER | `resolve_resource()`, `resolve_ga4_property()` | `connector_resource_resolver.py` |
| CONNECTOR_METADATA | linked property/site/customer in connector config | OAuth link flows |
| TIME_RESOLVER | ad hoc in marketing/analytics services | scattered |
| CAPABILITY_RECIPE | department recipes → capability_id | `capability_ontology/recipes.py` |
| ACTION_DEFAULT | schema `default` in JSON Schema | `action_parameters.py` |
| POLICY | governance scrub (e.g. `scrub_gmail_write_plan`) | `connector_action_workflows.py` |
| PREVIOUS_RESULT | `"output of step_N"` inference labels | parameter inference |
| MODEL_INFERENCE | `schema_param_extractor`, ReAct tool args | Module B Phase 2 |
| MUST_ASK_USER | clarification engine when ledger incomplete | `clarification_engine.py` |

### Audit questions

| Question | Answer |
|----------|--------|
| Asking user for derivable fields? | **Yes, sometimes** — GA4 property, GSC site, Slack channel should come from resolver/metadata; model still asked when resolver returns `not_found` |
| Allowing model to invent deterministic fields? | **Yes, risk** — inferred schemas + no preflight on ReAct path; e.g. HubSpot `filter_groups` structure |
| Explicit per-parameter source strategy? | **No** — ranking exists but no `ParameterSourceRule` on `ActionSpec` |

---

## E. Action Capability Completeness

| Connector | Provider API breadth | Gravitre exposure | Class | Business-relevant gap |
|-----------|---------------------|-------------------|-------|------------------------|
| google_analytics | Very large Reporting API | 7 actions | **PARTIAL** | No first-class campaign/geo/device/compare actions; model composes reports |
| google_search_console | Search Analytics + URL inspection | 4 actions | **PARTIAL** | No capability binding for website performance bundle |
| hubspot | Full CRM + marketing | 30 actions | **FULL** | Search/list duality |
| slack | Large Web API | 14 actions | **PARTIAL** | Covers messaging + channels; not full admin |
| salesforce | Very large | 14 actions | **PARTIAL** | Core CRM only |
| gmail | Gmail API | 9 actions | **PARTIAL** | Common mail ops |
| google_ads | Google Ads API | 10 actions | **PARTIAL** | Requires developer token + customer link |
| apollo | Sales intelligence | 17 actions | **PARTIAL** | Plan-gated discovery |
| mailchimp / hootsuite / notion | Large | 9–12 each | **MINIMAL** | Implemented but **no tests** |
| webhook | Custom | 3 catalog / 1 impl | **BROKEN** (2 ghosts) | Replay/get missing |

**Do not implement every provider operation** — audit identifies **business-relevant** subsets only.

---

## F. Capability Ontology ↔ Action Wiring

### Registered capabilities (9)

`crm.contact.create`, `crm.contact.search`, `messaging.channel.post`, `email.send`, `calendar.event.create`, `document.search`, `analytics.query`, `analytics.traffic_overview`, `payment.refund`

### Wiring audit

| Capability | Eligible providers | Resolved action | Resource req | Parameter recipe | Execution strategy |
|------------|-------------------|-----------------|--------------|------------------|-------------------|
| analytics.traffic_overview | google_analytics only | `google_analytics.reports.run` | GA4 property | **None structured** — model builds report body | Single invoke |
| analytics.query | google_analytics | same | GA4 property | None | Single invoke |
| crm.contact.search | hubspot, salesforce, pipedrive | per connected vendor | portal/org | search filters | `resolve_capability()` |
| messaging.channel.post | slack, microsoft_teams | `slack.post_message` / teams send | workspace | channel, text | governed write |

### Gaps

| Gap | Detail |
|-----|--------|
| Capabilities with **no executable action** when provider disconnected | Resolver returns `ok=false` — acceptable |
| Capabilities with **no binding** | "website performance" should include GSC — **missing** |
| Actions with **no capability mapping** | ~723 / 732 |
| Multi-action capabilities | Not modeled — `analytics.traffic_overview` should be recipe: GA4 + optional GSC |

**Department recipes** (`recipes.py`) use capability IDs correctly for sales/HR flows — good pattern to extend.

---

## G. Future Connector Contract

### Exists today (partial SDK)

Partner manifest (`connectors/sdk/manifest.py`) validates:

- `ConnectorManifest`, `ActionDefinition`, auth, triggers
- Registers via `connectors/sdk/registry.py`

### Canonical onboarding checklist vs reality

| Required artifact | Present? | Location |
|-------------------|----------|----------|
| ConnectorDefinition | Partial | `vendor_definitions.build_vendor()` |
| ProviderAuthDefinition | Yes | `oauth_provider_registry.py` |
| ResourceDefinition | **No** generic model | per-vendor adapters only |
| CapabilityMap | **No** | manual `capability_ontology/registry.py` |
| ActionDefinitions | Yes | ActionSpec |
| Schemas | Split | JSON + workflow + inferred |
| ParameterSourceRules | **No** | ad hoc ledger |
| GovernanceMetadata | Yes | kind, destructive, scopes, approval |
| ExecutionAdapter | Yes | tool_service / catalog_http |
| ObservationAdapter | Partial | `write_success_verification.py` |
| HealthCheck | Yes | `health_monitor_service.py` |
| Tests | CI audit | `audit_connector_catalog.py` |

### Special-case code still required

- Vendor `_extract_args` in `chat_action_mapper.py` (NL fallback)
- HubSpot scope map in `connector_availability_service.py`
- GA4 property resolver (not in adapter registry)
- Apollo discovery probe
- Google registry alias prefixes

**Verdict:** Future connectors can plug in via **SDK + catalog**, but **capability mapping, resource model, parameter rules, and NL fallbacks** still need manual work — not fully declarative.

---

## H. Connector Resource Model

### Implemented adapters (`RESOURCE_ADAPTER_REGISTRY`)

| Connector | resource_type | resource_id source |
|-----------|---------------|-------------------|
| hubspot | portal | config `portal_id` |
| salesforce | org | instance URL |
| slack | workspace | team_id |
| github | org | config org/login |
| microsoft365 | tenant | tenant_id |
| quickbooks | company | realm_id |
| google_search_console | site | linked site URL |
| google_ads | customer | linked customer id |
| google_analytics | property | **special** `resolve_ga4_property()` |

### Missing consistent fields

Ideal model: `resource_type`, `resource_id`, `display_name`, `canonical_identity`, `parent_resource`, `status`, `permissions`, `metadata`, `business_entity_mapping`.

**Actual:** `ResourceResolution` dataclass with `status`, `resource_type`, `resource_id`, `display_name`, `confidence`, `resolution_reason` — **no permissions**, **no business_entity_mapping**, **no parent hierarchy** (except implicit).

**77/85 vendors:** `resolver_not_implemented` → connection-only fallback.

---

## I. Action Discovery

### How planner learns actions

| Source | Role |
|--------|------|
| `build_connector_execution_matrix()` | Catalog ↔ registry ↔ chat_executable |
| `chat_tool_bridge.py` | Dynamic AgentToolSpec for connected org |
| `tool_service.list_registered_actions()` | Ground truth executors |
| `capability_ontology/tool_bridge.py` | `capability__*` synthetic tools |
| `connector_semantic_registry.py` | NL vendor aliases ("ga4", "gsc") |
| MCP sync | `mcp_catalog_sync.py` → runtime extensions |
| Partner SDK | manifest load |
| OpenAPI | **Reference only** (`vendor_contracts.py`) — no codegen |

### Can Gravitre answer "What can I do with this connector?"

**Yes, programmatically:**

- `GET /api/connectors/catalog/actions/{vendor}`
- `GET /api/connectors/catalog/execution-matrix?vendor=…`
- `evaluate_connector_availability(..., action_key=…)` per action

**Gaps:** No single user-facing capability-grouped view; model sees flat tool list via ReAct.

### Duplicates / mismatches

- Registry short names vs catalog long names (Google family) — aliased, not duplicated
- MCP `mcp_{server}` vendors may overlap manual catalog — extension merge in `extensions.py`
- Workflow builder uses same catalog via `connector-actions.ts` frontend types

---

## J. Action Availability vs Connector Health

| Check | Service | Granularity |
|-------|---------|-------------|
| Connector health | `health_monitor_service.py` | OAuth/token probe → row status |
| Action availability | `connector_availability_service.py` | **Per-action** when `action_key` passed |

`evaluate_connector_availability` checks: configured, authenticated, token_valid, scopes_valid (HubSpot map), action_registered, blocking_reason.

**Gap:** Planner/ReAct does **not consistently call** `evaluate_connector_availability(action_key=…)` before selecting a tool. Fresh intents go ReAct-first (`connector_chat_routing.should_run_connector_preflight` returns false).

**`CAN_THIS_ACTION_EXECUTE_NOW`:** Implemented as `app.services.action_execute_now.can_this_action_execute_now` (alias `CAN_THIS_ACTION_EXECUTE_NOW`). Applied before `tool_choice` in `narrow_tools_for_turn`, `embed_narrow_tools_for_turn`, and `narrow_permitted_tools_for_capability`. Uses connected/unavailable snapshots — **not** per-tool `evaluate_connector_availability(force_live=True)` and **not** HMAC preflight. See `docs/ai/PHASE_EXECUTE_NOW.md`.

---

## K. Action Limitations

| Limitation type | Encoded where? | Example |
|-----------------|----------------|---------|
| Unsupported metric/dimension combos | **nowhere** | GA4 runtime failures |
| Rate limits | `rate_limit.py` | generic |
| Scope restrictions | `connector_availability_service`, action scopes on spec | HubSpot per-action |
| API plan limitations | `apollo_discovery_capability.py` | Apollo search |
| Read-only endpoints | action `kind=read` | catalog |
| Max date ranges | **nowhere** | discovered at runtime |
| Pagination limits | partial in executors | inconsistent |
| Mutually exclusive args | **nowhere** | — |

**Anything discovered repeatedly at runtime should become structured action metadata** — currently **not** for GA4/GSC reporting constraints.

---

## L. Pre-Flight Action Validator

### Desired pipeline

```
ExecutionStep → resolve resource → resolve parameters → resolve credentials/scopes
  → validate action availability → validate schema → validate provider constraints
  → validate governance → execute
```

### Actual today

| Step | Governed chat | ReAct fresh intent | Workflow invoke |
|------|---------------|-------------------|-----------------|
| resolve resource | partial | **skip** | partial |
| resolve parameters | ledger + schema extractor | model args | gate_workflow_invoke |
| credentials/scopes | availability service | on invoke fail | on invoke fail |
| validate availability | sometimes | **skip** | sometimes |
| validate schema | workflow schema | JSON Schema (weak) | action_selection_gate |
| provider constraints | executor | executor | executor |
| validate governance | write gate | react_write_gate | write gate |

**Verdict:** **No single validation boundary.** Differs by path. `action_selection_gate` is closest for workflow; ReAct bypasses most preflight.

---

## M. Action Self-Repair

### Error classification (`tool_service._classify_error`)

Maps to: `connector_not_connected`, `channel_not_found`, `missing_scope`, `auth_expired`, `connector_timeout`, transport (generic), `validation_error`, rate limit.

**Not distinguished explicitly:**

- MISSING_DERIVABLE_PARAMETER vs MISSING_USER_PARAMETER
- INVALID_RESOURCE vs INVALID_SCHEMA
- UNSUPPORTED_OPERATION vs UNSUPPORTED_PARAMETER_COMBINATION
- PROVIDER_DATA_EMPTY

### Repair behaviors

| Failure | Current behavior |
|---------|-------------------|
| Missing params (governed) | Clarification / ledger resume |
| Missing params (ReAct) | Tool error → model retry or user message |
| Wrong tool | **No automatic switch** (deals.search vs deals.list) |
| Provider unavailable | `connector_not_connected` / honest skip |
| Schema mismatch | validation_error — **no self-repair** |
| Transport | retry (max 2) in invoke_tool |

`action_availability_honesty.py` rewrites model text claiming missing actions — **response repair**, not argument repair.

`cognitive_execution_replanner.py` exists but limited coverage.

---

## N. Cross-Connector Substitute Actions

| Business capability | Primary | Alternate | Supported? |
|--------------------|---------|-----------|------------|
| Website performance | GA4 | GSC | **No** — capability binds GA4 only |
| CRM contact lookup | HubSpot | Salesforce, Pipedrive | **Yes** — `crm.contact.search` multi-binding |
| Email send | Gmail | Outlook, SendGrid | **Yes** — `email.send` |
| Team message | Slack | Microsoft Teams | **Yes** — `messaging.channel.post` |

**Resolver:** `resolve_capability()` picks first connected+implemented binding; prefers mentioned vendor from context.

**Gap:** No structured fallback chain (GA4 down → try GSC for search performance slice).

---

## O. Action Test Coverage

| Class | Count | Notes |
|-------|------:|-------|
| verified_working | 482 | mock or live tests found |
| implemented_unverified | 248 | **no test files matched** |
| not_implemented | 2 | webhook |

### Coverage by test type (priority connectors)

| Connector | UNIT/SCHEMA | ADAPTER | INTEGRATION | LIVE |
|-----------|-------------|---------|-------------|------|
| hubspot | yes | yes | yes | yes |
| slack | yes | yes | yes | yes |
| google_analytics | partial | yes | oauth tests | partial |
| google_search_console | partial | yes | governance tests | smoke script |
| confluence | — | — | — | **NONE** (12/12) |

**Critical gap:** 248 actions marked `implemented_unverified` must not be marketed as production-verified (`claimNote` in audit JSON).

### Required tests (audit standard)

| Test type | Priority connectors | Long tail |
|-----------|--------------------|-----------|
| schema validation | CI lint + batch workflow tests | inferred only |
| resource-resolution | GA4, GSC, HubSpot | 77 vendors missing |
| parameter-resolution | Module B ledger tests | per-action gaps |
| execution-adapter | vendor tests | catalog_http stubs weak |
| error-recovery | HubSpot classification tests | sparse |
| governance (write) | write gate tests | high_risk flagged |
| live smoke | tier-1 | absent for 15+ vendors |

---

## P. Read / Write Governance

**Authority:** `catalog_write_authority.py` + `react_write_gate.py` + `risk_approval_evaluator.py`

Classification follows **action semantics** (kind, destructive, scopes), not connector name:

| Action | Classification |
|--------|----------------|
| slack.conversations.list | READ — auto-run eligible |
| slack.post_message | WRITE + EXTERNAL_COMMUNICATION — approval |
| hubspot.contacts.read/search | READ |
| hubspot.contacts.delete | DESTRUCTIVE_WRITE — approval |
| stripe.refunds.create | FINANCIAL write — approval |

**362 high_risk actions** flagged in audit. Scope suffixes on `kind=advanced` used as mutation signal.

**Verdict:** Governance **follows action spec** — PASS for catalog model. ReAct write gate enforces on tool path.

---

## Q. MCP / OpenAPI / Auto-Generated Actions

| Origin | Registration | Capability map | Resource resolution | Parameter rules | Governance | Validation | Observability | Testing |
|--------|--------------|----------------|--------------------|-----------------|------------|------------|---------------|---------|
| Manual adapter | full | manual | manual adapter | ledger | full | split schemas | audit_events | vendor tests |
| catalog_http | auto executor | **none** | connection only | inferred | catalog kind | executor only | audit_events | sparse |
| MCP sync | runtime extension | **none** | connection only | inferred | classified read/write | minimal | partial | `test_mcp_catalog_sync.py` |
| Partner SDK | manifest | **none** | manifest-defined | inputSchema | manifest flags | pydantic at ingest | audit_events | partner responsibility |

**Verdict:** Auto-generated actions **do not receive the same harness** as hand-built tier-1 connectors — **high risk** as connector count grows.

---

## R. Future Connector Acceptance Standard (PROPOSED — not implemented)

### Certification states

```
REGISTERED → CONFIGURED → CONNECTED → CAPABILITY_READY → ACTION_READY → PRODUCTION_VERIFIED
```

Do **not** collapse to single "connected" flag.

### Mandatory checklist (production-ready)

| Gate | Requirement |
|------|-------------|
| auth | OAuth/API key PASS |
| resource discovery | ResourceDefinition + adapter PASS |
| capability mapping | ≥1 business capability or explicit "action-only" |
| action schemas | Single canonical schema PASS |
| parameter sourcing | ParameterSourceRules for all required fields |
| preflight | Unified gate PASS |
| READ action | ≥1 live smoke PASS |
| WRITE action | governance + observation PASS where supported |
| error classification | STA-303 codes PASS |
| retry/replan | documented behavior |
| tenant isolation | org scoping PASS |
| live smoke | evidence-linked PASS per engineering standards |

---

## S. Connector Action Health Matrix

**Machine-readable:** `docs/delivery/connector-action-health-matrix.json`

### Platform rollup

| Metric | Value |
|--------|------:|
| Total actions | 732 |
| Business-relevant (catalog, non-scaffold) | 732 |
| Implemented | 730 |
| Executable (registry) | 730 |
| Schema-valid (catalog lint) | 732 |
| Resource-aware connectors | 9 / 85 |
| Parameter-aware (workflow schema) | ~730 writes + staged reads |
| Governed (write approval flagged) | 362 high_risk |
| Tested (any test) | 484 |
| Production-verified | 482 |

### P0 broken actions

| Action | Issue |
|--------|-------|
| `webhook.connectors.get` | catalog-only, not implemented |
| `webhook.post.replay` | catalog-only, not implemented |

### P1 incomplete actions

| Class | Count | Notes |
|-------|------:|-------|
| implemented_unverified | 248 | no automated test coverage |
| catalog_http stubs | unknown | long-tail vendors |

### P2 schema gaps

| Class | Notes |
|-------|-------|
| inferred-only schemas | GA4, GSC, many tier-3/4 vendors |
| cross-layer disagreement | HubSpot search class (fixed); risk remains class-wide |

### P3 missing coverage

Top vendors by `no_tests`: confluence (12), twilio (10), notion (10/12), freshdesk (9), gorgias (9), google_drive (9/12), hootsuite (8), n8n (8), aws_s3 (8).

### Per-connector sample (priority)

| Connector | Total | Impl | Tested | Verified | Resource-aware |
|-----------|------:|-----:|-------:|---------:|:--------------:|
| hubspot | 30 | 30 | 30 | 30 | Y |
| slack | 14 | 14 | 14 | 14 | Y |
| google_analytics | 7 | 7 | 7 | 7 | Y |
| google_search_console | 4 | 4 | 4 | 4 | Y |
| salesforce | 14 | 14 | 14 | 14 | Y |
| gmail | 9 | 9 | 9 | 9 | N |
| confluence | 12 | 12 | 0 | 0 | N |

---

## T. Critical Root-Cause Question

**Are Gravitre's recurring parameter failures primarily caused by one thing?**

**No.** They are **primarily a combination** of schema disagreement, missing preflight on ReAct path, parameter compilation across dual schemas, and tool-selection mismatch — with resource resolution and provider constraints as secondary contributors.

See [platform-autonomous-execution-review.md § Root-cause](./platform-autonomous-execution-review.md#root-cause-question-section-t-summary) for contribution table.

**Strongest single evidence chain:**

1. User asks for HubSpot deals → model picks `hubspot.deals.search` vs `hubspot.deals.list` (~tool-selection)
2. Search schema advertised optional criteria → executor required `filter_groups` (~schema wiring)
3. ReAct path did not run governed preflight or workflow validation (~missing preflight)
4. Error surfaced as generic "Invalid parameters" (~error classification, partially fixed STA-303)

---

## U. Platform Invariants to Evaluate

| ID | Invariant | Verdict | Evidence |
|----|-----------|---------|----------|
| K | Advertised capability → executable action or explicit unavailable | **PARTIAL** | 9 capabilities; disconnected → resolver fails honestly |
| L | One canonical schema per action | **FAIL** | JSON + workflow + executor trinity |
| M | Explicit source strategy per required param | **FAIL** | ledger ranks only |
| N | Preflight before every provider invoke | **FAIL** | ReAct-first bypass |
| O | Observation tied to plan_id/step_id | **PARTIAL** | audit_events with step_id; no uniform Observation type |
| P | Provider limitations structured | **FAIL** | GA4 combos, HubSpot filters runtime-discovered |
| Q | Future connector without cognitive special cases | **PARTIAL** | SDK yes; NL mapper fallbacks remain |
| R | Connected ≠ all actions available | **PARTIAL** | availability service supports; not always pre-plan |

---

## V. Do Not Implement Yet — Architecture Recommendation

This audit does **not** implement connector fixes. Recommended direction:

| Option | Recommendation |
|--------|----------------|
| Repair specific adapters | **Yes, targeted** — P0/P1 from live evidence (HubSpot template) |
| Strengthen action registry | **Yes** — single schema source of truth on ActionSpec |
| Strengthen capability mappings | **Yes** — expand beyond 9; add GA4+GSC recipes |
| Canonical parameter compilation | **Yes** — ParameterSourceRules consumed by ledger |
| Action preflight | **Yes** — extend `action_selection_gate` to all paths including ReAct |
| Standardize connector SDK/contracts | **Yes** — extend manifest with ResourceDefinition + ParameterSourceRules |
| New parallel subsystem | **No** |

**Prefer strengthening:** `action_catalog`, `connector_execution_matrix`, `action_selection_gate`, `connector_availability_service`, `parameter_ledger`, `capability_ontology`.

---

## Appendix: Audit regeneration

```bash
cd /workspace
python3 backend/scripts/audit_connector_catalog.py
# Updates docs/delivery/connector-catalog-audit-latest.json|.csv
```

Health matrix JSON generated from audit output + adapter registry inspection (2026-09-17).

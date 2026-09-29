# Gravitre product contract — core runtime ↔ 3.0 Plus frontend (Phase -1)

Date: 2026-09-28. Core = `main` @ `2807a089`. Frontend = `feat/gravitre-3.0-plus-frontend` @ `39ec95d5`.
Rule: one runtime, one product contract. The frontend renders canonical backend state and never invents it.

Status labels: WIRED (frontend reads the canonical source), PARTIAL (reads it but with an inferred, capped or mislabeled field), MISSING (no canonical source, or the frontend does not read it).
Every claim below comes from a code read or a local registry run. Anything that needs a production trace is marked NOT RUN.

---

## 1. Core capability inventory (main)

| Capability | Canonical id | Backend module | API / event | Schema | Tenant-scoped | R/W | Approval | Frontend consumer | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Agents | `operators.id` | `app/operators/router.py` (`agents_router`), `repository.py` | `GET/POST /api/agents`, `/api/operators/*` | `operators` (+ legacy `agents` FK target) | yes (`org_id`) | R/W | admin for create | Agents, Agent Detail, Dashboard | PARTIAL | Next BFF `/api/agents` reads Supabase directly and overrides FastAPI; the `agents` mirror write swallows errors (`repository.py:146`) |
| Agent trust | `agent_identity_records.trust_level` | `services/react_write_gate.py:351`, `voice_pstn_policy.py:145` | — | `agent_identity_records` | yes | R | — | Agent Detail | PARTIAL | Not enforced in `invoke_tool`; there is a second autonomy system, `operators.execution_mode` |
| Connector actions | ActionSpec `vendor.resource.verb` | `connectors/action_catalog/*` | `/api/connectors/catalog/*` | frozen dataclass, 85 vendors / 731 unique tools | catalog is global | R and W | 361 writes gated by `catalog_action_requires_write_approval` | Builder, Connectors, Marketplace | WIRED (builder now) | Catalog endpoints are not org-scoped; `risk_class` is filled only for the F1 slice; no output schema |
| Connectors | `connectors.id` | `connectors/repository.py`, `connection_health.py` | `/api/connectors*` | `connectors` (`vendor`/`type`, `status`) | yes | R/W | admin | Connectors, Sources, Builder | WIRED | Usable = `ACTIVE_CONNECTOR_STATUSES` {active, connected, syncing, healthy}; `GET /plaid/status` is shadowed by `/{connector_id}` |
| Tool invocation | `tool.invoke.*` audit | `services/tool_service.py` | `/api/tools/invoke`, chat | `audit_events` | yes | R/W | HITL + `write_governance` + HMAC | AI Workspace (protected) | WIRED | No-HITL WRITE default is approval-required. Unattended WRITE requires `trust_level=autonomous` and `approval_rule_overrides.write=auto_run`. F1 always-approval. `GET /api/capabilities` exposes the composed view. |
| Workflows | `workflows.id` | `app/workflows/*` | `/api/workflows`, `/execute`, `/dry-run`, `/runs/{id}/approve` | `workflows`, `workflow_runs`, `workflow_steps` (+ legacy `workflow_defs`) | yes | R/W | approval step, `SAFE_DEFAULT_APPROVER_ROLES` | Workflows, Builder, Schedules | WIRED (list now proxied) | Approval not atomic; trigger_type CHECK mismatch (retry/salesforce/segment/pagerduty) |
| Workflow primitives | step type | `workflows/constants.py` | — | 11 step types | n/a | n/a | `approval` step | Builder | WIRED | `transform` is dry-run only (not in `EXECUTE_ALLOWED_STEP_TYPES`) |
| Schedules | `workflow_schedules.id` | workflows scheduler | `/api/workflows/schedules*` | `workflow_schedules` | yes | R/W | — | Schedules | WIRED | — |
| Cognitive turn | turn id | `CognitiveTurnKernel` | `/api/assistant/chat` SSE (start, text-delta, tool-*, data-intelligence, data-suggestions, finish) | `cognitive_turn_traces`, `conversations.task_state` | yes | R/W | PendingAction claim RPC | AI Workspace (protected) | WIRED | ExecutionPlan / Observation / work_artifacts live only in `task_state` (no tables) |
| Governance | `org_id` context | `get_org_context`, `require_admin`, `require_tier`, `hitl_policies` | `/api/approvals`, governance routes | `audit_events`, `audit_logs`, `hitl_policies` | yes (service role + `.eq(org_id)`) | R/W | — | Approvals, Governance | PARTIAL | No audit HMAC or hash chain; older RLS policies use `LIMIT 1`; audit rows are dropped when actor/resource is not a UUID |
| Knowledge | rag doc id | `rag_*`, `knowledge_fabric`, `org_knowledge_nodes` | `/api/rag/*`, `/api/knowledge/*` | rag tables | rag yes; `knowledge_fabric` shared | R/W | — | Sources, Intelligence | PARTIAL | `knowledge_fabric` is not org-scoped |
| Run outcomes | `workflow_runs.id` | `services/execution_outcome.py` (`finalize_execution_outcome`, single terminal writer) | notification + learning events | `workflow_runs`, `intelligence_outcome_events` | yes | W (internal) | — | Activity, Dashboard | WIRED | Terminal statuses: completed / failed / cancelled / partial_success / flagged_for_review |
| Business outcomes | projection of runs | `/api/business-outcomes` projector | — | none (projection) | yes | R | — | Dashboard (Measure), Intelligence | PARTIAL | Kernel `_stage_verify` always passes; the honest verified / accepted_unproven / unverified states live in the projector |
| Metrics definitions | `metric_key` | `services/cognitive_metrics.py` | `/api/admin/cognitive-metrics*` | `org_metric_definitions` (definitions only) | yes | R/W admin | — | none | MISSING in UI | Platform defaults MQL/CAC/ARR are Cesar-authorized definition text; no value store |
| Attribution / ROI | action outcome row | `agent_roi_service`, `agent_action_outcomes` | `/api/admin/intelligence/business-impact` | `agent_action_outcomes` | yes | R | — | Dashboard | PARTIAL | Correlational; only 3 actions: `hubspot.deals.update`, `stripe.subscriptions.update`, `quickbooks.invoices.create`; ROI = measured cost + estimated labor |
| Signals | event type | `services/intelligence_outcome_path.py` | `recommendation_created`, `prediction_generated` | `intelligence_outcome_events` | yes | R | — | Intelligence, Dashboard | PARTIAL | Churn advisory is suggest-only and gated on labeled training rows (`churn_advisory_service.py`) |
| Notifications | event type | `services/notification_emitter.py` | 15 canonical types | `notifications` | yes | R | — | Bell, Activity | PARTIAL | CHECK constraint lacks `run_cancelled`, `run_flagged_for_review` |
| Write verification | mode | `services/write_success_verification.py` | — | JSON catalog | n/a | n/a | — | Activity, chat results | PARTIAL | 282 implemented writes are `accepted_async` only (vendor accepted, never re-read) |
| Council | — | council service | — | not persisted | — | — | — | Builder council step | PARTIAL | Sessions are not persisted |

## 2. Frontend inventory (3.0 Plus)

| Surface | Data required | Current API | Hook / source | Mock / fixture | Real backend | Wiring gap | Protected seam | Regression risk |
|---|---|---|---|---|---|---|---|---|
| Dashboard | KPIs, agents, approvals, outcomes, learning | `/api/metrics/overview`, `/api/agents`, `/api/approvals`, 5× `/api/admin/*`, ops-summary, `/api/settings/dashboard-layout` | `hooks/use-home-dashboard-data.ts`, `lib/dashboard/kpi-registry.ts` (27 KPIs) | none | yes | 5 admin-only calls → 403 for members; overview only 7d/30d/90d; trust-summary ignores `periodDays`; ops-summary 24h / 500-row cap; "Most used model" = configured frequency, not usage | no | medium |
| AI Workspace | chat, plans, pending actions, artifacts | `/api/assistant/chat` SSE | `ai-workspace.tsx` | none | yes | Main-only additions (`executionResult.structured`, new artifact kinds, `CanonicalArtifactTable`) are not on this branch | **yes** | high (merge) |
| Assignments | jobs, steps, owner | `/api/assignments` | `lib/assignments-list.ts` | `lib/demo-assignments.ts` | yes | Steps / role / destination are inferred client-side | no | medium |
| Agents | list, status, stats | Next BFF `/api/agents` | `app/api/agents/route.ts` | none | Supabase direct | BFF overrides FastAPI; `tasksToday` = lifetime runs; department inferred "Operations"; model "auto" | no | medium |
| Agent Detail | agent, stats, trust | Next BFF `/api/agents/[id]` | route handler | none | Supabase direct | Second source of truth; label fixed to "Total runs" in this phase | no | low |
| Approvals | pending approvals | `/api/approvals` (FastAPI) | — | none | yes | — | no | low |
| Workflows | list, run stats | `/api/workflows` → FastAPI proxy + `nodes` join | `app/api/workflows/route.ts` | none | yes | Fixed in this phase (was a Supabase-direct BFF that skipped Lite-seat filtering) | no | low |
| Workflow Builder | graph, connectors, actions | `/api/workflows/*`, `/api/connectors`, catalog | `app/workflows/[id]/builder/page.tsx` | legacy `connectorActions`, fallback council personas, invented debate content (~L1614–1630, 1866–1875) | yes | Mock seed graph and mock connector library removed in this phase; council fallbacks remain | no | medium |
| Schedules | schedules | `/api/workflows/schedules` | — | none | yes | — | no | low |
| Goals | goal, progress | Next `/api/goals/**` (Supabase direct) | route handlers | none | Supabase direct | Invented percentage removed in this phase; now "Not measured" | no | low |
| Activity | runs, audit | runs / audit endpoints | — | none | yes | — | no | low |
| Connectors | vendors, status | `/api/connectors`, catalog | page | hard-coded shipped / coming-soon list | partly | Duplicates the catalog `shipped` flag | no | medium |
| Sources | rag sources | `/api/rag/*` | — | none | yes | — | no | low |
| Marketplace | listings | `/api/marketplace/*` | — | none | yes | — | no | low |
| Intelligence | insights, predictions | `/api/admin/intelligence/*`, meson | — | intelligence-drawer default timings | yes | Meson insights 403 for lower tiers | no | medium |
| Model Studio | models | model routes | — | — | partial | Agent model only in `agents.model` | no | low |
| Governance | policies, audit | governance routes | — | none | yes | — | no | low |
| Marketing API docs | endpoint list | static | `app/(marketing)/api/page.tsx` | — | n/a | Paths fixed in this phase; public mdx still references removed `/api/operator/*` (5 files); SDK install claims (`@gravitre/sdk`, `pip install gravitre`) unverified | no | low |

## 3. Contract matrix

| Product concept | Canonical backend source | API / event | Frontend surface | Status |
|---|---|---|---|---|
| Agent | `operators` | `/api/agents` (FastAPI) | Agents, Agent Detail | PARTIAL (Next BFF bypass) |
| Agent trust / autonomy | `agent_identity_records.trust_level` + `operators.execution_mode` | — | Agent Detail | PARTIAL (two systems) |
| Connector | `connectors` + `ACTIVE_CONNECTOR_STATUSES` | `/api/connectors` | Connectors, Builder | WIRED |
| Action (READ/WRITE) | ActionSpec + `catalog_write_authority` | `/api/connectors/catalog/actions` | Builder | WIRED |
| Approval-required action | `catalog_action_requires_write_approval`, `hitl_policies` | `/api/approvals` | Approvals | WIRED |
| Workflow | `workflows` / `workflow_runs` | `/api/workflows` | Workflows, Builder | WIRED |
| Schedule | `workflow_schedules` | schedules API | Schedules | WIRED |
| Chat execution | CognitiveTurnKernel | `/api/assistant/chat` SSE | AI Workspace | WIRED (branch lacks main's artifact kinds) |
| Assignment | assignments API | `/api/assignments` | Assignments | PARTIAL (inferred steps) |
| Goal progress | none | — | Goals | MISSING (shown as "Not measured") |
| Run outcome | `finalize_execution_outcome` | notifications / outcome events | Activity, Dashboard | WIRED |
| Business outcome | runs projector | `/api/business-outcomes` | Dashboard Measure | PARTIAL |
| Business metric value | none (definitions only) | — | Dashboard KPIs | MISSING |
| Attribution | `agent_action_outcomes` | business-impact | Dashboard | PARTIAL (3 actions, correlational) |
| Signal | `intelligence_outcome_events` signal events | intelligence routes | Intelligence | PARTIAL |
| Evidence chain | audit + traces + verification | spread across routes | Activity, run detail | PARTIAL (no single contract) |
| Capability registry | `app/capabilities/registry.py` (new, local only) | internal | none yet | PARTIAL (not exposed) |
| Play | none | — | none | MISSING |

## 4. Wiring gaps

Fixed in Phase -1D (frontend commit `39ec95d5`):
- Builder shipped a mock "Customer Data Pipeline" graph and a mock connector library. It now starts empty and validates against real org connectors and the ActionSpec catalog (`lib/workflows/builder-connector-validation.ts`).
- The workflow card showed invented connector dependencies; it now shows only what the caller passes.
- `/api/workflows` GET bypassed FastAPI and lost Lite-seat filtering and run stats; it now proxies FastAPI and joins `nodes`.
- Goal progress invented a percentage from unrelated org runs; it now shows 100 only when completed, otherwise "Not measured".
- Agent Detail labeled lifetime runs as "Tasks today"; it now shows "Total runs" when that field is present.
- Dashboard 1h/24h ranges silently showed 7-day data; the label now says so.
- The marketing API page listed nonexistent endpoints; paths are corrected. No new claims were added.

Open (convergence items, not new capability):
- `/api/agents` and `/api/agents/[id]` Next BFFs duplicate FastAPI and infer department / model / `tasksToday`.
- Assignments infer steps, role and destination client-side.
- The Connectors page hard-codes shipped/coming-soon instead of reading catalog `shipped`.
- Builder council fallbacks: personas and debate content are invented when the backend returns nothing.
- Five Dashboard calls are admin-only (403 for members); trust-summary ignores `periodDays`.
- Public docs mdx still reference the removed `/api/operator/*`.
- Main's artifact / `executionResult.structured` additions must land on the branch before merge (protected seam; requires a merge, not a re-implementation).

Backend gaps (need a Cesar decision; not touched):
- `trust_level` is not enforced in `invoke_tool`.
- `operators` vs `agents` FK split.
- No audit HMAC or hash chain.
- Workflow approval is not atomic.
- CHECK-constraint mismatches (trigger_type, notification type).
- Plaid route shadowing.
- Council sessions are not persisted.

## 5. Registry architecture (Phase -1E)

Module `backend/app/capabilities/registry.py` (read-only, no tables, no endpoint yet). It composes existing sources and keeps no catalog of its own:

| Question | Function | Canonical source |
|---|---|---|
| Agents | `list_agents(client, org_id)` | `operators.repository.list_operators` |
| Connectors | `list_connectors()`, `connected_vendors(client, org_id)` | vendor catalog, `connectors.repository.list_connectors`, `is_connector_usable` |
| Actions, READ vs WRITE | `list_actions(vendor, access, implemented_only)`, `get_action(tool)` | ActionSpec catalog, `catalog_action_requires_write_approval`, registered `invoke_tool` handlers |
| Approval-required actions | `approval_required_actions()` | same write-authority gate the runtime uses |
| Workflow primitives | `workflow_primitives()` | `ALLOWED_STEP_TYPES`, `EXECUTE_ALLOWED_STEP_TYPES` |
| Signals / events | `event_taxonomy()` | `intelligence_outcome_path`, `outcome_learning_service`, `notification_emitter`, `execution_outcome.TERMINAL_STATUSES` |
| Business metrics | `business_metrics(client, org_id)` | `cognitive_metrics` (platform defaults + org overrides) |
| Data hooks | Section 9 of this doc | Dashboard hook endpoints |
| Evidence | `evidence_sources()` | maps the six evidence states onto existing stores |
| Verification | `verification_mechanisms()` | `write_success_verification`, BusinessOutcome projector states |
| Play dependencies | `resolve_dependencies(connectors, actions, connected)`, `connector_readiness`, `action_readiness` | all of the above |

Readiness rules:
- MISSING: the vendor or action is not in the catalog, or has no registered handler.
- PARTIAL: the action is in the catalog but has no registered handler.
- EXTERNAL_CONNECTION_REQUIRED: the action is implemented but the org has no usable connector for it, or no org context was given (unknown connection state is never reported as AVAILABLE).
- AVAILABLE: the action is implemented and the org's connector is usable.

"Implemented" means an `invoke_tool` handler is registered (dedicated or catalog-HTTP). It is not proof that the handler has run live.

Local registry run (`2807a089` + registry):
- 85 vendors; 731 unique tools; 729 with a handler.
- 362 write, all approval-gated; 361 of them implemented.
- Write verification modes: `accepted_async` 283, `follow_up_entity_get` 75, `follow_up_membership` 3, `follow_up_field_assert` 1.
- Tests: `backend/tests/test_capability_registry.py`, 12 passed.

## 6. Play readiness matrix

Readiness is computed with `connected=None` (no org context). Every implemented dependency therefore reads EXTERNAL_CONNECTION_REQUIRED until a real org's connectors are resolved. Nothing here is a claim that a Play is live.

### Customer Rescue

| Dependency | Item | Readiness | Notes |
|---|---|---|---|
| Signal | churn risk (`prediction_generated`) | PARTIAL | `churn_advisory_service` is suggest-only and needs labeled rows (`training_gate_status`) |
| Signal | open / escalated tickets | EXTERNAL_CONNECTION_REQUIRED | `zendesk.tickets.list`, `intercom.conversations.list`, `freshdesk.tickets.list` (read) |
| Required connectors | one CRM (hubspot or salesforce) + one support tool (zendesk / intercom / freshdesk) | EXTERNAL_CONNECTION_REQUIRED | all implemented |
| Optional connectors | slack, gmail / outlook | EXTERNAL_CONNECTION_REQUIRED | |
| Agents | an org operator | EXTERNAL_CONNECTION_REQUIRED (org data) | no Play-specific agent exists; must not be seeded |
| Actions | `zendesk.tickets.update`, `intercom.conversations.reply`, `hubspot.contacts.update`, `slack.post_message` | EXTERNAL_CONNECTION_REQUIRED | all writes are approval-gated |
| Approvals | write gate + `hitl_policies` + `write_governance` | AVAILABLE | no HITL rows → ACT WITH APPROVAL, not auto-run |
| Verification | `zendesk.tickets.update` / `hubspot.contacts.update` = `follow_up_entity_get`; `intercom.conversations.reply`, `slack.post_message` = `accepted_async` | PARTIAL | |
| Outcome metric | retained account / churn avoided | MISSING | no metric definition or value store; `crm_won`/`crm_lost` are the closest events |

### Revenue Recovery

| Dependency | Item | Readiness | Notes |
|---|---|---|---|
| Signal | failed / overdue customer payments | PARTIAL | readable via `stripe.invoices.list`, `quickbooks.invoices.list`; no detector emits a signal (`past_due` exists only in Gravitre's own billing) |
| Required connectors | stripe or quickbooks | EXTERNAL_CONNECTION_REQUIRED | |
| Optional connectors | hubspot / salesforce, gmail / outlook, slack | EXTERNAL_CONNECTION_REQUIRED | |
| Agents | an org operator | EXTERNAL_CONNECTION_REQUIRED (org data) | |
| Actions | `stripe.subscriptions.update`, `stripe.invoices.create`, `quickbooks.invoices.create`, `hubspot.deals.update` | EXTERNAL_CONNECTION_REQUIRED | approval-gated |
| Approvals | write gate | AVAILABLE | |
| Verification | `stripe.subscriptions.update`, `quickbooks.invoices.create`, `hubspot.deals.update` = `follow_up_entity_get`; `stripe.invoices.create` = `accepted_async` | PARTIAL | |
| Outcome metric | recovered revenue | PARTIAL | ARR definition exists (platform default); attribution covers `stripe.subscriptions.update`, `quickbooks.invoices.create`, `hubspot.deals.update` (correlational) |

### Marketing Performance

| Dependency | Item | Readiness | Notes |
|---|---|---|---|
| Signal | spend / performance change | PARTIAL | readable via `google_ads.reports.performance`, `google_analytics.reports.run`, `meta_marketing.campaigns.list`; no anomaly detector |
| Required connectors | google_ads or meta_marketing; google_analytics | EXTERNAL_CONNECTION_REQUIRED | |
| Optional connectors | hubspot / marketo, linkedin, mixpanel | EXTERNAL_CONNECTION_REQUIRED | |
| Agents | an org operator | EXTERNAL_CONNECTION_REQUIRED (org data) | |
| Actions | `google_ads.campaigns.pause`, `google_ads.campaigns.update_budget`, `meta_marketing.adsets.update` | EXTERNAL_CONNECTION_REQUIRED | approval-gated |
| Approvals | write gate | AVAILABLE | |
| Verification | all three actions are `accepted_async` | PARTIAL | the vendor accepted the call; nothing re-reads it |
| Outcome metric | CAC / MQL | PARTIAL | definitions exist (platform defaults); no value store; no ROAS definition |

## 7. Existing outcome architecture

1. Run terminal: `finalize_execution_outcome` is the single writer. It writes `workflow_runs`, the audit action (`workflow.execute.*`), the notification (`run_*`) and the learning event (`workflow_*`) into `intelligence_outcome_events`.
2. Learning taxonomy (`outcome_learning_service`): `TOOL_SUCCESS_EVENTS` (execution evidence) is kept separate from `BUSINESS_IMPACT_EVENTS` (proof of change). The code explicitly says execution is not business improvement.
3. BusinessOutcome: a projection over runs with verified / accepted_unproven / unverified. The kernel's own verify stage always passes, so the projector is the honest layer.
4. Attribution: `agent_action_outcomes`, correlational, 3 actions.
5. Metrics: definitions only (`org_metric_definitions` + Cesar-authorized MQL/CAC/ARR defaults). No KPI values, no `business_outcomes` table.

## 8. Existing evidence architecture → the six states

| State | Existing store | Gap |
|---|---|---|
| SIGNAL | `intelligence_outcome_events` (`recommendation_created`, `prediction_generated`), connector read results | No detectors for payments / spend |
| CONTEXT | `cognitive_turn_traces`, rag / knowledge nodes, `conversations.task_state` | Observations are not persisted as rows |
| RECOMMENDATION | `recommendation_created`, recommendations (advisory) | — |
| ACTION | `audit_events` (`tool.invoke.*`, `workflow.execute.*`), `workflow_steps` snapshots, `run_hash` | No HMAC or hash chain; non-UUID actor rows dropped |
| VERIFICATION | `write_success_verification`, `workflow_runs.verified_output`, projector states | 283 writes are `accepted_async` only |
| OUTCOME | `OUTCOME_RESULT_EVENTS`, `agent_action_outcomes` | No value store |

These states must stay separate in every Play and dashboard surface. "Action completed" is never shown as "outcome achieved".

Maturity levels (-1G) use the existing gates, with the same Play code at every level:
- OBSERVE: read actions only; the registry filter is `access="read"`.
- RECOMMEND: emits `recommendation_created`; no `invoke_tool` (the churn advisory pattern).
- ACT WITH APPROVAL: write actions through the catalog write gate and `/api/approvals`.
- ACT WITHIN POLICY: writes auto-run only when `write_governance` authorizes this agent/context (`autonomous` + `auto_run`, and no covering HITL). Absence of HITL rows is ACT WITH APPROVAL, not this level.

## 9. Dashboard data hooks

Source: `apps/web/hooks/use-home-dashboard-data.ts`.

| Endpoint | Notes |
|---|---|
| `/api/onboarding` | |
| `/api/metrics/overview?range=` | 7d / 30d / 90d only |
| `/api/agents` | Next BFF |
| `/api/approvals` | |
| `/api/admin/intelligence/trust-summary` | admin; ignores `periodDays` |
| `/api/admin/intelligence/business-impact` | admin |
| `/api/admin/intelligence/learning-progress` | admin |
| `/api/admin/learning/live-dashboard` | admin |
| `/api/admin/ai-os/status`, `predictive-ops` | admin |
| `/api/admin/learning/status` | |
| `/api/assignments?limit=50` | |
| ops-summary | 24h, max 500 rows |
| `/api/settings/dashboard-layout` | `user_ui_preferences` |

Day-one value (-1H) may come only from these, fed by real connected data. When a source is empty or 403, the surface shows "not connected" or "not measured", never a number.

## 10. OPEN architecture decisions (Cesar)

1. **Registry delivery.** The registry is committed locally on `main` and NOT pushed, because a push to `main` deploys production. Choose: push as-is (internal module, no route), or also add a read-only `/api/capabilities` route for the frontend.
2. **Agent source of truth.** Retire the Next `/api/agents` BFFs in favor of FastAPI `agents_router`, or keep them and fix the inferred fields.
3. **Autonomy.** Canonical invoke-tool resolver is `write_governance.resolve_write_user_approval` (HITL + `trust_level` + `approval_rule_overrides` + F1). `operators.execution_mode` remains workflow auto-execute only; it is not a second invoke_tool gate. Default: no HITL rows → approval required for WRITE.
4. **Evidence integrity.** Add an audit HMAC / hash chain and persist Observations, or keep them in `task_state`.
5. **Business metric values.** Add a value store (e.g. `kpi_values`) so Play outcomes can be measured. Without it, outcome metrics stay MISSING/PARTIAL.
6. **Signal detectors.** Failed-payment and spend-anomaly detectors for Revenue Recovery and Marketing Performance. This is new capability, so it is out of scope for convergence and needs explicit approval.
7. **Merge order.** Main's artifact / `executionResult.structured` work must merge into the frontend branch (touches the protected chat panel) before the frontend merges to main.
8. **Public claims.** Confirm the `@gravitre/sdk` / `pip install gravitre` install lines on the marketing site, or remove them; also fix the mdx still citing `/api/operator/*`.
9. **Master Program text.** The Phase 0+ Master Program referenced by the directive was not found in the repo or past chats. Provide it, or confirm the priority order in -1J (convergence → registry → Play abstraction → outcome/evidence contract → three Plays → dashboard outcomes → live Play proof → dataset providers) is the program.

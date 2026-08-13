# Cognitive-system proposal — reconciliation audit (standing reference)

**Status:** Diagnosis only — no build plan, no code changes in this pass  
**Product:** Gravitre  
**Date:** 2026-08-13  
**Question:** Of the 20-item “genuine cognitive system” proposal, how much is already shipped — and does what exists function as **one coherent system** or as coexisting mechanisms?  
**Evidence bar:** Claims are grounded in code paths, migrations, services, or prior delivery artifacts. Local presence ≠ production PASS. Labels: **FULLY / PARTIALLY / NOT** vs the proposal wording (not “code exists somewhere”).  
**Update rule:** Refresh this document when Module B memory scope, Knowledge Fabric schema, unified-turn composition, council/swarm behavior, BusinessOutcome learning loop, eval batteries, or dual-path (ReAct vs governed chat) wiring change. Same discipline as `gravitre-routing-decision-map.md` and Tool Knowledge reconciliations.

**Related standing refs**

| Doc | Path |
|-----|------|
| Routing decision map | `docs/delivery/gravitre-routing-decision-map.md` |
| Tool Knowledge Phase 0 / Phase 5 / closeout | `docs/delivery/tool-knowledge-phase0-reconciliation.md`, `tool-knowledge-phase5-governance-reconciliation.md`, `tool-knowledge-closeout.md` |
| Module B architecture leftovers | `docs/delivery/module-b-architecture-reference.md` |
| Memory fuzzy-match product decision | `docs/delivery/memory-fuzzy-match-product-decision.md` |
| Prior cohesion canvas (2026-07-19) | Cursor canvas `master-intelligence-cohesion-audit.canvas.tsx` |

---

## Executive verdict

Almost none of the 20 items are **FULLY** built against the proposal’s cognitive-system wording. Most are **PARTIALLY** built: real, valuable mechanisms exist (working/conversation memory, Knowledge Fabric, research cascade, HITL approvals, BusinessOutcome, council/swarm, eval batteries, golden signals). A few are **NOT** built as specified (authoritative metrics semantic layer; business what-if simulation).

The harder finding: **parts do not yet compose as one brain.** The densest composition path is `AgentIntelligence.execute_task` (retrieve → memory → company intel → entity graph → tools → optional LIVE unified turn → optional critic). Adjacent stacks — governed chat HITL, Meson planners, outcome learning, council, proactive guidance, desktop notifications — often fire in the same product without a single unifying “thinking sequence,” and Engineering Standards still require independent dual-path verification (ReAct vs governed chat).

**Starting implication:** the highest-leverage next work is **integration coherence**, not inventing twenty new subsystems.

---

# Part A — Item-by-item reconciliation

| # | Proposal item | Status | What exists (real) | What’s missing vs proposal |
|---|---------------|--------|--------------------|----------------------------|
| 1 | Persistent agent memory (working/episodic/preference/decision/outcome/relationship/procedural) | **PARTIALLY** | Working: `working_memory_profile.py`. Conversation: `conversation_memory_engine.py` (`task_state.conversation_memory`). Cross-convo ledger: `cross_conversation_ledger_memory.py` + `org_entity_resolution_records` (email/Slack channel slots; flag-gated). Vector store: `agent_memories` + `agent_memory_service.py` (fact/preference/pattern/rule). Promotion candidates: `memory_promotion_service.py`. Hybrid: `hybrid_memory_service.py`. Outcomes as execution records: BusinessOutcome package — not personal memory. | No first-class taxonomy covering decision/outcome/relationship/procedural as durable cognitive types. Cross-conversation is **narrow ledger slots**, not full episodic recall. Fuzzy person match Option C **not authorized** (`memory-fuzzy-match-product-decision.md`). |
| 2 | Organizational knowledge graph | **PARTIALLY** | `org_entity_relationships` + `entity_relationship_builder.py` / `entity_relationship_service.py` / `knowledge_graph_service.py`. Injected into ReAct prompts via `build_entity_context_section`. Admin intelligence relationships tab. Departments on agents + dept RAG (`DEPARTMENT_RAG.md`). Knowledge Fabric is **platform packs**, not the tenant org chart. | Not a productized company/employees/customers/vendors graph. Edges are best-effort from connectors/workflows/glossary. GNN marked planned, not shipped (`INTELLIGENCE_ENGINE_V3_V6_TABLES.md`). |
| 3 | Temporal knowledge (`valid_from` / `valid_until` / `superseded_by`) | **PARTIALLY** | Fabric docs: `effective_at`, `superseded_at`, `published_at`, `version_label` on `knowledge_documents`; chunk `freshness_score` / `authority_score`; source `effective_date_sensitive`, `refresh_days`; `knowledge_fabric/refresh.py`. Wave2 closeout docs. | Those exact field names **do not exist**. No bi-temporal edge lineage / `superseded_by` FK graph. |
| 4 | Agent planning before execution + dynamic replanning | **PARTIALLY** | `task_state.current_plan`; conversational planning; Module B turn controller; plan-bar/SSE progress; ReAct thought→tool loop (`react_engine.py`); Meson `generate_workflow` (`meson_service.py`). Advisory plan-first tests. | Meson ≠ Module B planner (**explicitly deferred**). No first-class mid-flight cognitive replan; pending-family modify/cancel + ReAct re-iterate are substitutes. |
| 5 | Reflection/critic on consequential outputs | **PARTIALLY** | `verification_critic_service.py` (`verify_before_delivery` from `agent_intelligence.py`). `reflection_loop_service.py` (OIL). Module A verified completion + `batch_degeneracy.py` (never claim verified on degenerate batches). | Critic is lightweight/optional Tier-2, not mandatory for every consequential write/recommendation. |
| 6 | Evidence-based answers (recommendation + why + sources + confidence) | **PARTIALLY** | Conversational behavior prompt rules; Knowledge Fabric `KnowledgeCitationCard` / explainability panels; BusinessOutcome evidence UI; Module C honesty delivery artifacts; research cascade provenance (`research_manager.py`). | Not a uniform chat DTO `{recommendation, why, sources, confidence}` on every path. Citations strongest on KF/transparency, not every connector reply. |
| 7 | Confidence scoring with behavior thresholds | **PARTIALLY** | `confidence_honesty.py` (source labels, estimate flags); Module C live JSON shows heuristic when models unloaded; orchestrator `finalize_confidence`; thresholds in `intelligence_engine_settings.py` / sync confidence; Module B high/medium/low propose/ask; acoustic honesty `voice_acoustic_signal.py`. | No single cognitive behavior-policy table. Many scores remain **explicitly heuristic** by design. |
| 8 | Autonomous research mode | **PARTIALLY** | Research Manager cascade + `adaptive_research_cascade.py`; Serper primary (`web_research.py`, STA-341 ship); metering; KF router via `unified_turn_knowledge_context.py`. | No separate user-facing “Autonomous Research Mode” product toggle — research is embedded in normal chat cascade. |
| 9 | Cross-agent collaboration / challenge | **PARTIALLY** | Swarm (`swarm_coordinator_service.py`); Council (`council_service.py`, `AgentRole.SKEPTIC`, multi-round); Command-tier gate; workflow council step; UI `/multi-agent-run`. | **Not interactive debate.** Prompt requires independent evaluation and forbids influence by other members; rounds re-sample until vote consensus. Changelog honesty: aggregated after completion, not live shared memory. |
| 10 | Agent specializations within departments | **PARTIALLY** | Named seeded agents (e.g. SEO Marketing Analyst, Lead Enrichment Coordinator); `persona_service.py` departments; dept RAG; catalog department tags; swarm subtask scoping. | No recursive “department umbrella → many sub-agents with shared departmental memory” product model. |
| 11 | Company operating model inference | **PARTIALLY** | `organization_process_inventory`; process mining patterns; `CompanyIntelligenceOrchestrator` + scheduler → `## Learned Company Intelligence` in system prompt; digital twin reads inventory. | No learned approval thresholds or automatic adoption of process sequences as the agent’s operating model. |
| 12 | Outcome learning → future recommendations | **PARTIALLY** | `OutcomeLearningService` / `intelligence_outcome_events`; Module A finalize → learning; BusinessOutcome verified lifecycle; recommendation quality / domain optimization engines; Mode A human-approved framing in program docs. | Closed loop is correlational / Mode A, not automatic policy update. Impact edges intentionally sparse until real data. Population-verify gap still named on routing map. |
| 13 | Business metrics semantic layer (MQL/CAC/ARR SoT) | **NOT** | Org glossary/clusters and marketplace “metric definitions” copy are not an authoritative KPI semantic layer. | No per-company enforced MQL/CAC/ARR definition tables/APIs. |
| 14 | Proactive agents (unprompted findings) | **PARTIALLY** | `ProactiveGuidanceService` (in-chat, suppressed in clarify/execute); advisor briefs on-demand; `GET /api/activity/recent`; notification center; desktop companion (native notify/approve still PARTIAL per desktop delivery). | No standing unprompted investigation agents that push “3 issues found” without a user turn. |
| 15 | Watchers/triggers | **PARTIALLY** | Workflow cron schedules; inbound vendor webhooks → workflows; outbound webhooks; `external_signals`; company-intel / metrics cron. | Triggers mostly start **workflows**, not free-form investigation agents. |
| 16 | Simulation mode (“what if spend −30%”) | **NOT** (vs proposal) | Workflow digital twin / dry-run exists (`workflows/digital_twin.py`). `DigitalTwinService.SIMULATION_REFUSAL` explicitly keeps predictive multi-step what-if **out of scope**. | No counterfactual business scenario engine. |
| 17 | Role-based agent permissions (field-level) | **PARTIALLY** | Org RLS; `agent_tool_permissions` (tool scopes); Lite seat USE/CONFIGURE (`seat_context.py`, entitlements); department RAG / HITL department scope. | **No field-level / column-level** CRM ACL for agents. |
| 18 | Explainable pre-action cards | **PARTIALLY** | Chat confirm / step HITL (`chat-execution-panel.tsx`); Approvals page (approve/reject + advisory reason/confidence); BusinessOutcome shows approval **status**; optimization insights have impact/risk for workflow recs. | Closest UX ≈ **40–50%** of the described card. Missing structured expected impact + risk + **modify** as a single pre-action object on Activity/Outcomes. Actions live on chat/Approvals; Activity is largely projection. |
| 19 | Agent evaluation framework (unified, all agents, every change) | **PARTIALLY** | Separate batteries: NL-variance / withhold_no_tool unit battery; catalog NL-variance GH workflow; F1–F10 ledger on routing map; conversational-behavior scorer + live scripts; `check-chat-surface-drift.mjs` in CI; many ad-hoc `verify-*-live.py`. | **Not one unified suite** that re-runs all agents on every prompt/model/knowledge-pack change. |
| 20 | Agent observability console | **PARTIALLY** | Admin golden-signals panel; `audit_events` + Audit UI; job `react_trace`; unified-turn latency metadata; workflow node debug + BusinessOutcome. | No single per-run console joining intent routing + retrieval + tools + tokens + cost + latency + confidence. |

### Part A scoreboard

| Status | Count | Items |
|--------|------:|-------|
| FULLY | 0 | — |
| PARTIALLY | 18 | 1–12, 14–15, 17–20 |
| NOT | 2 | 13 (metrics SoT), 16 (business what-if; twin refuses) |

---

# Part B — Does it function as ONE system?

## B1 — Do memory, knowledge, tools, governance, and honesty compose?

**Honest answer: they compose on the densest path; they do not compose universally.**

### Concrete composition path (code-traced)

`AgentIntelligence.execute_task` in `backend/app/operators/agent_intelligence.py` (~1030–1140, LIVE fork ~1653, critic ~3106):

1. **Plan** — `resolve_plan(...)`
2. **Retrieve (knowledge + memory)** — `UnifiedRetrievalService.retrieve(...)` → `rag_section`, `memory_section`, `org_context`
3. **Company intel** — `CompanyIntelligenceOrchestrator.get_context_for_prompt`
4. **Entity graph** — `build_entity_context_section`
5. **Prompt assembly** — `_build_task_prompt` / `_build_system_prompt` (RAG + memory + company intel + entity relationships + honesty/boundary rules + conversational behavior)
6. **Tools** — `get_agent_tools` + tool permission asserts
7. **LIVE fork** — when enabled, `apply_unified_turn_live(...)` (governed unified turn); else classical/ReAct
8. **Optional critic** — `VerificationCriticService.verify_before_delivery`

On this path, memory retrieval and knowledge retrieval **do** land in the same system prompt, and tools run under agent tool permissions. That is real composition.

### Where composition breaks

| Pair | Reality |
|------|---------|
| ReAct / LIVE chat vs governed connector HITL | Dual pipelines; standards require independent verification until one gate |
| BusinessOutcome / outcome learning → next recommendation | Events recorded; not automatic policy rewrite |
| Process mining / inventory → planner | Inventory exists; agents don’t auto-adopt sequences as operating model |
| Council members | Parallel independent votes, not shared-scratchpad debate |
| Meson planner vs Module B planner | Explicitly not unified |
| Extension enrich / workflow / most webhooks | Often **never** enter `apply_unified_turn_live` (routing map A3–A6) |
| KF citations vs connector replies | Honesty/citations not uniform across all answer surfaces |
| Proactive guidance vs desktop notifications | Separate stacks; desktop notify/approve still PARTIAL |

**Illustrative complex request** (architecture-level, not a single production audit_events row claimed as PASS here):  
User asks in main chat to research a prospect, recommend a CRM write, and await approval.

| Stage | Systems that can touch it | Interplay? |
|-------|---------------------------|------------|
| Intake | Assistant chat → `execute_task` / LIVE | Shared entry when LIVE enabled |
| Context | Unified retrieval (RAG + `agent_memories`), company intel, entity relationships | Composed into one prompt on ReAct path |
| Research | Research Manager / Serper cascade if confidence/stage gates fire | Can add provenance; not always KF citation cards |
| Plan / confirm | Conversational plan + chat execution panel HITL | Governance real; not full explainable impact/risk/modify card |
| Write | Catalog write authority / confirm token | Real gate |
| After | BusinessOutcome projection + optional outcome events | Learning does not reliably reshape the next turn’s policy |
| Parallel surfaces | Extension enrich, Meson, Approvals page, Activity feed | Often parallel UIs on related facts, not one cognitive loop |

Without a specific conversation/run id from prod for this narrative, treat the table as **architecture composition evidence**, not a live PASS claim.

## B2 — Is there one “thinking sequence”?

**No.** Behavior today is a **stack of separately triggered mechanisms** with one relatively dense assembly point (`execute_task` / LIVE), not a single mandatory sequence:

> retrieve → recall memory → check knowledge → plan → verify → govern → act → learn

Actual shape (simplified):

- Feature flags / pending-family resume / pack-common / classical defer (routing map)
- Optional LIVE unified turn **or** classical ReAct
- Separate HITL confirm path for connector writes
- Optional research cascade stages
- Optional critic
- Async company-intel cron and outcome-event recording **outside** the turn
- Council/swarm only on Command-tier / workflow nodes

That is “many brain-adjacent parts with a shared UI and some shared prompt assembly,” not “one brain.”

## B3 — Most consequential **integration** gaps

Ranked by coherence impact (not feature novelty):

1. **Dual execution brains** — ReAct/LIVE vs governed chat HITL vs Meson/workflows vs extension direct actions (routing map).
2. **Outcome learning does not close into planning/recommendations** — store without steering.
3. **Memory taxonomy fragmented** — conversation memory, ledger slots, `agent_memories`, promotion candidates, BusinessOutcome are parallel stores.
4. **Entity graph / Knowledge Fabric / company intel** share a prompt on one path but are not one org knowledge product.
5. **Council looks collaborative but is independent parallel voting.**
6. **Eval + observability are shards** — many probes, no unified agent regression console / per-run join.

---

# Part C — Honest recommendation

## C1 — Rank confirmed gaps (value × cost discipline)

| Rank | Gap | Value | Cost / risk | Notes |
|------|-----|-------|-------------|-------|
| 1 | **Integrate dual paths into one governed turn sequence** (or hard shared gates) | Very high | High | Unlocks coherence for items 4–7, 18 without new product surface |
| 2 | **Close outcome → recommendation loop (Mode A, measured)** | High | Medium | Uses BusinessOutcome / `intelligence_outcome_events` already built |
| 3 | **Unify explainable pre-action card** (impact/risk/modify) on chat + Approvals, project to Activity | High | Medium | Extends proven HITL UI (~halfway already) |
| 4 | **Cross-conversation memory product scope** (beyond email/channel ledger) | High | High + governance | **Product decision required** |
| 5 | **Org knowledge graph as intentional product** (vs CRM-derived edges) | High | High + data | **Product decision required** |
| 6 | **Unified eval harness** (wire existing batteries) | High for safety | Medium | Mostly orchestration of what exists |
| 7 | **Per-run observability join** (audit + react_trace + latency + confidence) | High for ops | Medium | Console over existing signals |
| 8 | Metrics semantic layer (MQL/CAC/ARR) | Medium–high for GTM claims | High | Greenfield SoT |
| 9 | True council debate / challenge | Medium | Medium | Behavior change to council prompts + shared scratchpad |
| 10 | Business what-if simulation | Medium | Very high | Explicitly out of scope today |
| 11 | Field-level permissions | Medium | Very high | RLS redesign |
| 12 | Unprompted proactive investigators + watchers→agents | Medium | High | New runtime model |

## C2 — Items that need Cesar’s product decision before engineering

| Decision | Why engineering alone is insufficient |
|----------|----------------------------------------|
| **Persistent cross-conversation memory scope** | Expanding beyond ledger slots / exact+role cues touches privacy, PII, and the already-gated Option C embeddings path (`memory-fuzzy-match-product-decision.md`). |
| **Organizational knowledge graph as a product surface** | Choosing CRM-derived edges vs intentional company/employee/customer/vendor model changes schema, UX, and liability for wrong relationships. |
| **Authoritative metrics definitions (MQL/CAC/ARR)** | Semantic layer is a company-truth product, not a retrieval tweak. |
| **Business what-if simulation** | Explicitly refused in `DigitalTwinService`; enabling it is a product-boundary change. |
| **Field-level agent permissions** | Crosses seat model, RLS, and CRM vendor realities — entitlement design, not a tool flag. |

## C3 — Recommended starting point

**Start with integration, not the 20-item feature list.**

1. Treat “one thinking sequence on the main chat path” as the north star: memory + KF/RAG + tools + write governance + honesty labels + outcome recording must share one turn contract on **both** LIVE and classical fallthrough, with extension/workflow gaps named rather than silently assumed.
2. Only after that contract is real, expand memory/graph — and only after Cesar’s named decisions on scope.
3. Do **not** greenfield simulation, field-level ACL, or a second research mode until composition and Mode A learning feedback are honest.

---

## Appendix — Key file index (non-exhaustive)

| Area | Paths |
|------|-------|
| Composition spine | `backend/app/operators/agent_intelligence.py`, `unified_retrieval_service.py`, `unified_turn_reasoning_service.py` |
| Memory | `conversation_memory_engine.py`, `cross_conversation_ledger_memory.py`, `agent_memory_service.py`, `memory_promotion_service.py`, `working_memory_profile.py` |
| Knowledge | `backend/app/knowledge_fabric/*`, `entity_relationship_service.py`, migrations `platform_knowledge_fabric`, `entity_relationships_v6` |
| Research | `research_manager.py`, `adaptive_research_cascade.py`, `web_research.py` |
| Governance / outcomes | `chat-execution-panel.tsx`, Approvals page, `business_outcome/*`, `outcome_learning_service.py` |
| Council / swarm | `council_service.py`, `swarm_coordinator_service.py` |
| Honesty | `confidence_honesty.py`, Module C delivery JSON under `docs/delivery/` |
| Eval | `test_routing_nl_variance_battery.py`, `check-chat-surface-drift.mjs`, conversational-behavior live scripts |
| Observability | `golden_signals_service.py`, `audit_events`, job `react_trace` |

---

*End of diagnosis. Append future reassessments as dated sections; do not overwrite Part A/B evidence.*

---

## Phase 0–9 implementation status (2026-08-13)

Append-only status vs the One Brain / CognitiveTurnKernel plan. Labels: **CODE** = present in repo; **LIVE PENDING** = needs prod/chat evidence before PASS.

| Phase | Scope | Status |
|-------|--------|--------|
| 0 | Binding architecture doc | **CODE** — `docs/delivery/cognitive-turn-kernel-architecture-2026-08.md` |
| 1 | Kernel + migration + streaming intake | **CODE** — `cognitive_turn_kernel.py`, migration `20260813120000_*`; streaming kernel-before-LIVE; **LIVE PENDING** prod re-run |
| 2 | Knowledge merge + planner + entry adapters | **CODE** — knowledge layer, planner, extension/council adapters |
| 3 | Field ACL + govern hooks | **CODE** — `cognitive_field_acl.py` wired in GOVERN |
| 4 | Outcome → PLAN bias (Mode A) | **CODE** — `cognitive_outcome_loop.bias_from_outcomes` in kernel |
| 5 | Org metrics SoT admin API | **CODE** — `cognitive_metrics` service + `/api/admin/cognitive-metrics` |
| 6 | Honest what-if simulation | **CODE** — `cognitive_simulation_service` + admin POST what-if (heuristic, Module C) |
| 7 | Admin cognitive turns console | **CODE** — admin Learning tab "Cognitive turns" + list/detail API |
| 8 | Regression suite in CI | **CODE** — `scripts/cognitive-regression-suite.mjs` in `ci.yml` |
| 9 | Unit tests + evidence checklist | **CODE** — `test_cognitive_turn_kernel.py`; `docs/delivery/one-brain-phase-evidence-2026-08.md` |

Product decisions still gated (unchanged): fuzzy person-name Option C out; cross-org memory never; metrics/what-if must not invent customer SKU prices.

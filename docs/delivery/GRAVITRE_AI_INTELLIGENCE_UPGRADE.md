# Gravitre AI Intelligence Upgrade — 2026-06-08

Principal-engineer audit of agents, workflows, Meson, RAG, and assistant against the Gravitre Operating Model. This document is the Phase 1–2 discovery + gap analysis deliverable. Phase 3 backend implementation (B1–B8) is scoped as a follow-on sprint sequence — not all items are shipped in this commit.

---

## Section 1 — Discovery Summary

### Architecture map (what exists)

| Layer | Key paths | Status |
|-------|-----------|--------|
| Model routing | `backend/app/services/model_router.py`, `providers/*`, `ai_guardrails.py` | **Strong** — multi-provider failover, guardrails, billing |
| Assistant | `backend/app/routers/assistant.py` | **Partial** — governed completion, 3 tools, pseudo-stream |
| Operators / jobs | `backend/app/operators/agent_jobs.py`, `operators/router.py` | **Partial** — durable queue, single-shot LLM plan |
| RAG | `backend/app/rag/*`, `services/rag_service.py` | **Good** — ingest, pgvector, hybrid RRF, lexical rerank |
| Workflows | `backend/app/workflows/execute.py`, `builder_sync.py`, `dry_run.py`, `digital_twin.py` | **Partial** — sequential steps, graph compile, no runtime graph engine |
| Handoffs | `backend/app/services/handoff_service.py`, `b2b_handoff_service.py` | **Good** — intra-org + B2B |
| Meson (product) | `apps/web/components/gravitre/meson-wizard.tsx`, billing `meson_addons` | **UI only** — wizard mock; no copilot backend |
| Conversations | `supabase/migrations/20260604120000_assistant_conversations.sql`, `routers/conversations.py` | **Schema + CRUD** — not wired to `/api/assistant/chat` |
| Fine-tuning | `backend/app/ml/fine_tuning.py`, `routers/training.py` | **Present** — training hub UI errors on load (prod) |

### What does **not** exist (requested in spec)

| Artifact | Expected path | Found |
|----------|---------------|-------|
| `AgentIntelligence` | `operators/agent_intelligence.py` | ❌ |
| `ReActEngine` | `operators/react_engine.py` | ❌ |
| Role prompts (Sales/Marketing/…) | `operators/agent_prompts.py` | ❌ |
| `WorkflowExecutionEngine` (graph batches) | `workflows/execution_engine.py` | ❌ |
| `MesonService` | `services/meson_service.py` | ❌ |
| `/api/meson/*` | `routers/meson.py` | ❌ |
| `OrgContextService` | `services/org_context_service.py` | ❌ |
| True token streaming | `model_router.stream()` | ❌ |
| Cross-encoder reranking | `sentence-transformers` in RAG | ❌ (lexical rerank only) |

### Live checks (2026-06-08)

| Endpoint | Result |
|----------|--------|
| `https://gravitre.app/assistant` | HTTP 307 (auth redirect — expected) |
| `https://gravitre-saas-backend-production.up.railway.app/health` | HTTP 200 |
| Connectors list (post-fix `62e2981`) | Fixed NameError; redeploy required |
| Training hub (screenshot) | UI shows "Failed to load some training data" — investigate prod proxy/auth |

### Scores **before** upgrade work

| Dimension | Score | Evidence |
|-----------|-------|----------|
| Agent intelligence | **4/10** | Jobs call `model_router.complete` once; no ReAct, no per-task RAG, generic operator prompt |
| Workflow execution correctness | **6/10** | Steps run in order; `builder_sync` topologically compiles graph; no parallel batches at runtime |
| Meson intelligence | **2/10** | Wizard UI + billing addons; no watch/learn/suggest backend |
| RAG quality | **6/10** | Hybrid search + RRF; rerank is token overlap, not cross-encoder |
| Assistant context awareness | **5/10** | 3 org-scoped tools; no org context block; chat not persisted |
| Streaming quality | **3/10** | Full completion then chunked SSE (`_TEXT_DELTA_CHARS = 24`) |
| Cross-agent collaboration | **6/10** | `handoff_service` + federation APIs; not universal on all agents |
| **Overall** | **4.5/10** | Strong platform bones; intelligence layer not unified |

---

## Section 2 — Agent Intelligence

### Current behavior

1. **Agent jobs** (`agent_jobs.py:265–275`) — One `router.complete()` call with `TaskType.WORKFLOW_PLANNING` and `get_operator_system_prompt()`. Returns structured plan fields. **No tool loop, no RAG retrieval, no clarification path.**

2. **Handoffs** (`handoff_service.py`) — Structured briefing JSON, `execute_agent_step_with_handoff` injects briefing into prompt. **Good foundation for B1.**

3. **UI agents page** (screenshots) — Rich v0 visuals (topology, metrics). Backend stats often come from `agents.stats` JSON — not live ReAct traces.

4. **Department agents** — Created via marketplace packs / Meson wizard config; execution still flows through operators/jobs, not role-specific prompt library.

### Required behavior (gap)

| Gap | Current | Required | Fix |
|-----|---------|----------|-----|
| Universal intelligence layer | Per-path ad hoc LLM calls | `AgentIntelligence.execute_task()` | **B1.1** |
| Role personas | Generic operator prompt | Sales/Marketing/Finance/… prompts | **B1.2** |
| ReAct tool loop | Single completion | Reason → act → observe loop | **B1.3** |
| RAG before respond | Assistant + RAG query endpoint only | Top-k chunks per agent task | Wire `RAGService.query(..., agent_id=)` in B1 |
| Clarification | Not implemented | `needs_human_input` result | ReActEngine branch |

### Target score after B1: **8/10**

---

## Section 3 — Workflow Execution

### Current behavior

1. **`execute_workflow_steps`** (`execute.py:77–150`) — Iterates `definition.steps` **sequentially**. Passes `step_outputs` dict downstream. Supports branch skip via `resolve_active_branch`, interrupts, council.

2. **`builder_sync._topological_node_order`** — Compiles visual graph → ordered steps when saving builder. **Runtime does not re-walk graph**; it trusts compiled step list.

3. **Digital twin** (`workflows/digital_twin.py`) — Simulation without side effects (STA-120). Intelligence drawer simulate tab is **client-side heuristic only** (not wired to API yet).

4. **Parallel execution** — No `asyncio.gather` batch in `execute.py`.

### Required behavior (gap)

| Gap | Current | Required | Fix |
|-----|---------|----------|-----|
| Graph-native execution | Compiled linear steps | Topological batches + parallel fan-out | **B2** `WorkflowExecutionEngine` |
| Node input briefing | `step_outputs` partial | Full upstream context per node | Extend `_build_node_input` in B2 |
| Approval pause/resume | Partial (run statuses) | Explicit pause at approval nodes | B2 + existing approvals router |
| Per-node retry policy | Limited | retry / skip / fail_workflow | B2 |

### Target score after B2: **8/10**

---

## Section 4 — Meson

### Current behavior

1. **`meson-wizard.tsx`** — 5-step UI wizard ("Build with Meson"). Generates **mock** config client-side. Matches marketing screenshots.

2. **Billing** — `meson_addons` catalog in settings/billing; not an AI copilot.

3. **Adjacent intelligence (not Meson-branded)**:
   - `integration_suggestion_service.py` — audit-based connector/workflow suggestions (STA-123)
   - `workflow_failure_prediction_service.py` — pre-failure alerts (STA-122)
   - Intelligence drawer — local simulate heuristics; risk scan uses `listFailurePredictions` not scan endpoint

### Required behavior (gap)

| Gap | Current | Required | Fix |
|-----|---------|----------|-----|
| Workflow builder suggestions | None | POST `/api/meson/suggestions` | **B3** |
| Anomaly alerts | Failure predictions only | Unified Meson alerts | **B3** + wire CS dashboard |
| Optimization tips | None | Per-workflow recommendations | **B3** |
| Preference learning | None | User model/workflow prefs | **B3** |
| Builder panel UI | None | v0 prompt F1 | Frontend (v0 branch) |

### Target score after B3 + F1: **7/10**

---

## Section 5 — Assistant

### Current behavior (`assistant.py`)

- **Guardrails**: killswitch, rate limit, budget, moderation, fencing — ✅ production-grade
- **Tools**: `knowledge_base`, `agent_status`, `connector_status` only
- **Context**: Last 12 messages in memory from request body — **not loaded from DB**
- **Streaming**: `router.complete()` then `_build_stream()` splits answer into 24-char chunks — **not token streaming**
- **Persistence**: No `conversation_id` in chat request/response
- **Org context**: Static system prompt; no live org state injection

### Conversations API (exists but disconnected)

- Tables: `conversations`, `conversation_messages` (migration `20260604120000`)
- Router: `GET/POST/PATCH/DELETE /api/conversations`
- Assistant page: sidebar shows "No conversations" — **frontend not listing; backend chat not writing**

### Required behavior (gap)

| Gap | Fix |
|-----|-----|
| Persist chat | **B4** — wire chat to conversations tables |
| True streaming | **B8** — `model_router.stream()` + SSE tokens |
| Org context pill | **B6** + **F4** frontend |
| Expanded tools | **B7** — run_agent_task, analytics, create_workflow, etc. |
| Mode selector (Fast/Deep/Agent) | **F4** — pass `task_complexity` to router |

### Target score after B4+B6+B7+B8+F4: **9/10**

---

## Section 6 — v0 Frontend Prompts (F1–F4)

**Do not implement in Cursor.** Paste into v0.dev. Full text also in [`docs/design/V0_AI_INTELLIGENCE_PROMPTS.md`](../design/V0_AI_INTELLIGENCE_PROMPTS.md).

| ID | Target | Summary |
|----|--------|---------|
| **F1** | Workflow builder | Meson copilot side panel — suggestions, alerts, optimizations |
| **F2** | Agents list/detail | Intelligence signals on cards (success rate, knowledge, last task) |
| **F3** | Run monitor | Sequential pipeline timeline with approval gates |
| **F4** | Assistant page | Conversation sidebar, mode selector, org context pill, follow-ups |

---

## Section 7 — Test Results

| Suite | Result |
|-------|--------|
| `pytest` (backend) | **621 passed** (2026-06-08, post v0 merge) |
| `pnpm exec tsc --noEmit` (web) | **Clean** |
| `pnpm run build` (web) | **Passed** |
| Meson API smoke | **N/A** — endpoints not implemented |
| Assistant streaming smoke | **Pseudo-stream only** — full response buffered first |

---

## Section 8 — Revised Scores (after v0 UI merge, before B1–B8)

| Dimension | Before | After v0 UI only | After B1–B8 (target) |
|-----------|--------|------------------|---------------------|
| Agent intelligence | 4/10 | 4/10 | 8/10 |
| Workflow execution | 6/10 | 6/10 | 8/10 |
| Meson intelligence | 2/10 | 3/10 (wizard UI) | 7/10 |
| RAG quality | 6/10 | 6/10 | 8/10 |
| Assistant | 5/10 | 5/10 | 9/10 |
| Streaming | 3/10 | 3/10 | 8/10 |
| Cross-agent collaboration | 6/10 | 6/10 | 8/10 |
| **Overall** | **4.5/10** | **4.7/10** | **8/10** |

---

## Final Verdict

**Today:** Gravitre has production-grade AI **governance** (model router, guardrails, billing, RAG ingest, workflow execution, handoffs, federation). It does **not yet** have a unified **intelligence layer** where every agent runs ReAct + RAG + tools, Meson proactively coaches builders, or the assistant streams tokens with persistent memory and full org awareness.

**After v0 UI merge (`51e33f0`):** CS Command Center, role packs, federation hub, builder intelligence drawer (heuristic simulate), and connector recommendations improve **discoverability** — but backend intelligence gaps above remain.

**Recommended implementation order (Phase 3):**

1. **B4** — Wire assistant chat ↔ conversations (highest user-visible win)
2. **B8** — True streaming in model router + assistant
3. **B6** — Org context service (unblocks assistant + agents)
4. **B1** — AgentIntelligence + ReActEngine
5. **B3** — MesonService + `/api/meson/*`
6. **B2** — Graph-native WorkflowExecutionEngine
7. **B5** — Cross-encoder reranking (optional dependency weight)
8. **B7** — Expanded assistant tools

**v0 next:** Run prompts F1–F4 on branch `v0/cesarbohorquezjr-4251-8b623736`, then merge to `main` preserving backend (same process as `51e33f0`).

---

## Appendix — Key file references

```text
model_router.complete     backend/app/services/model_router.py:143
assistant pseudo-stream   backend/app/routers/assistant.py:433-461
agent job LLM             backend/app/operators/agent_jobs.py:265-275
workflow sequential       backend/app/workflows/execute.py:77
graph compile             backend/app/workflows/builder_sync.py:42
RAG hybrid rerank         backend/app/services/rag_service.py:157-275
handoff briefing          backend/app/services/handoff_service.py:45
meson wizard UI           apps/web/components/gravitre/meson-wizard.tsx
conversations API         backend/app/routers/conversations.py
intelligence drawer       apps/web/components/workflows/intelligence-drawer.tsx:147-166
```

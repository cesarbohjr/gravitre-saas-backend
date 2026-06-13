# Gravitre AI/ML Production Readiness Report

**Linear:** [STA-172](https://linear.app/staqbot/issue/STA-172) · **Parent:** [STA-131](https://linear.app/staqbot/issue/STA-131) Discovery & Verification  
**Updated:** 2026-06-13 · **Deploy commit:** `c768f28` (F1–F4 UI) · **Prior audit:** [GRAVITRE_AI_INTELLIGENCE_UPGRADE.md](GRAVITRE_AI_INTELLIGENCE_UPGRADE.md) (STA-155)

This is the canonical **Phase 2 operational gap / production readiness** deliverable. It supersedes the June 7 snapshot in [`AI_ML_OPERATIONAL_GAP_REPORT.md`](AI_ML_OPERATIONAL_GAP_REPORT.md) for current status.

**Legend:** **EXISTS** = implemented in repo · **WIRED** = UI/API connected end-to-end · **MISSING** = not implemented or not prod-verified · **PARTIAL** = shipped with known gaps

---

## Executive summary

| Area | Status | Score (now / target) |
|------|--------|----------------------|
| Agent intelligence (ReAct, personas, RAG-in-task) | **WIRED** | 7/10 → 8/10 |
| Workflow execution (graph engine, approval, I/O logs) | **WIRED** | 8/10 → 8/10 ✓ |
| Meson (interpret, deploy, copilot) | **WIRED** | 7/10 → 7/10 ✓ |
| RAG (hybrid + cross-encoder rerank) | **EXISTS** | 7/10 → 8/10 |
| Assistant (stream, history, org context, tools) | **WIRED** | 9/10 → 9/10 ✓ |
| Conversations CRUD + chat persistence | **WIRED** | — |
| Integrations as tools (`invoke_tool`) | **WIRED** | — |
| Frontend E2E (Epic I + F1–F4) | **WIRED** | — |
| **Overall** | **Production-ready for AI ops** | **7.8/10 → 8/10** |

**Prod smoke:** `npm run smoke:ai-production` — **15/15 pass** ([`smoke-ai-production-latest.json`](smoke-ai-production-latest.json), 2026-06-13)  
**Backend tests:** **803 passed** ([STA-156 verification](STA-156_PHASE5_VERIFICATION.md))

---

## Component matrix (EXISTS / WIRED / MISSING)

| Component | Status | Evidence |
|-----------|--------|----------|
| `AgentIntelligence.execute_task()` | **EXISTS · WIRED** | `backend/app/operators/agent_intelligence.py:282` |
| `ReActEngine` tool loop | **EXISTS · WIRED** | `backend/app/operators/react_engine.py:117`; jobs at `agent_jobs.py:376` |
| Role personas (`AGENT_PERSONAS`) | **EXISTS · WIRED** | `backend/app/operators/agent_prompts.py` (used by AgentIntelligence) |
| Agent jobs → ReAct (not plan-only) | **WIRED** | `backend/app/operators/agent_jobs.py:376` |
| Graph `WorkflowExecutionEngine` | **EXISTS · WIRED** | `backend/app/workflows/execution_engine.py`; runtime `execution_engine_runtime.py:1` |
| Approval pause / resume | **WIRED** | `workflows.py:2637` (`resume_workflow_graph`); run UI `apps/web/app/runs/[id]/page.tsx` |
| Per-node I/O snapshots in run API | **WIRED** | `workflows.py:486` (`inputSnapshot`, `outputSnapshot`, `stepType`) |
| `MesonService` + `/api/meson/*` | **EXISTS · WIRED** | `backend/app/services/meson_service.py:166`; `backend/app/routers/meson.py:139` |
| Meson copilot panel (F1) | **WIRED** | `apps/web/components/workflows/meson-copilot-panel.tsx:1`; builder `page.tsx` toolbar |
| Cross-encoder RAG rerank | **EXISTS** | `backend/app/rag/hybrid_rerank.py:117` (`_cross_encoder_rerank`) |
| Semantic chunking | **EXISTS** | `backend/app/rag/ingest.py` (default `semantic` strategy) |
| `OrgContextService` | **EXISTS · WIRED** | `backend/app/services/org_context_service.py:73`; assistant `assistant.py:826` |
| True token streaming | **WIRED** | `model_router.py:521` (`stream`); `assistant.py:575` (`prepare_stream` + `stream`) |
| Conversation CRUD | **EXISTS · WIRED** | `backend/app/routers/conversations.py`; web `/api/conversations/*` |
| Chat ↔ conversation persistence | **WIRED** | `assistant.py:735` (`conversation_id` + persist) |
| `invoke_tool` connector layer | **EXISTS · WIRED** | `backend/app/services/tool_service.py:2477` |
| Agent list knowledge doc count API | **MISSING** | UI mocks count — `apps/web/app/agents/page.tsx:83` (`TODO`) |
| Per-step retry API (not full-run retry) | **MISSING** | Run UI retries via `runsApi.retry(id)` only |
| Resume workflow run from `paused` | **PARTIAL** | Pause/cancel wired; no dedicated resume UX |

---

## 1. Agents

| Item | Status | File:line |
|------|--------|-----------|
| Universal intelligence layer | **WIRED** | `agent_intelligence.py:257` (`AgentIntelligence`) |
| RAG before agent task | **WIRED** | `agent_intelligence.py` → `RAGService.query(..., agent_id=)` |
| ReAct reasoning + tool trace | **WIRED** | `react_engine.py:117`; smoke `agent_job: trace_steps=1` |
| Role-specific system prompts | **WIRED** | `agent_prompts.py`; `get_agent_persona()` (STA-174) |
| Assign Task UI → `/api/agent-jobs` | **WIRED** | `apps/web/app/assignments/new/page.tsx`, `hooks/use-async-job.ts` |
| Agent-scoped chat | **WIRED** | `apps/web/app/agents/[id]/chat/page.tsx` |
| Agent card intelligence (F2) | **WIRED** | `apps/web/app/agents/page.tsx:77` (metrics, model badge, knowledge pill) |
| Live knowledge doc count on `/api/agents` | **MISSING** | Frontend derives mock when API field absent (`page.tsx:83`) |

**Remaining gap:** Expose `knowledge_doc_count` (or training dataset count) on operator/agent list API so F2 knowledge pill is fully data-driven.

---

## 2. Workflows

| Item | Status | File:line |
|------|--------|-----------|
| Graph-native execution engine | **WIRED** | `execution_engine.py`; `execute.py:70` delegates to graph path |
| Parallel batch execution | **EXISTS** | `execution_engine_runtime.py:1`, `:346` (`parallel_batch`) |
| Human approval gates | **WIRED** | Engine pause + `runs/[id]/page.tsx` approval UI |
| Run/Preview → execute + dry-run | **WIRED** | `builder/page.tsx`; `lib/workflows/run-monitor.ts` |
| Execution timeline (F3) | **WIRED** | `apps/web/components/runs/execution-timeline.tsx` |
| Step input/output in run detail API | **WIRED** | `workflows.py:486` (`_run_step_out`) |
| Digital twin simulation | **WIRED** | `workflows/digital_twin.py`; smoke pass |
| Run pause / cancel / rollback UI | **WIRED** | `runs/[id]/page.tsx`; smoke `run_interrupt_routes` |

**Remaining gap:** Dedicated per-step retry endpoint; resume-from-paused workflow run action in UI.

---

## 3. Meson

| Item | Status | File:line |
|------|--------|-----------|
| `POST /api/meson/interpret` | **WIRED** | `meson.py`; wizard `meson-wizard.tsx` |
| `POST /api/meson/deploy` | **WIRED** | Creates agent + optional workflow |
| `POST /api/meson/suggestions` | **WIRED** | `meson.py:139`; smoke `meson_copilot_routes` |
| `GET /api/meson/alerts` | **WIRED** | `meson.py:159` |
| `GET /api/meson/insights` | **WIRED** | `meson.py:178` |
| Next.js proxies | **WIRED** | `apps/web/app/api/meson/*/route.ts` (8 routes) |
| Meson copilot panel (F1) | **WIRED** | `meson-copilot-panel.tsx`; builder Meson toggle |
| Feedback loop (accept/dismiss) | **WIRED** | `mesonApi.feedback`; panel + builder |

**Remaining gap:** Optimization “Apply” buttons are UI-only (no auto-apply workflow mutation yet).

---

## 4. RAG

| Item | Status | File:line |
|------|--------|-----------|
| Ingest + pgvector storage | **EXISTS** | `backend/app/rag/ingest.py`, `worker.py` |
| Hybrid retrieval (vector + lexical) | **EXISTS** | `backend/app/rag/hybrid_rerank.py` |
| Cross-encoder rerank (STA-150) | **EXISTS** | `hybrid_rerank.py:170` (`_cross_encoder_rerank`) |
| Semantic chunking (STA-171) | **EXISTS** | Default `semantic` strategy in ingest |
| Agent-scoped retrieval in tasks | **WIRED** | `AgentIntelligence` + `RAGService.query` |
| Department / org RAG scopes | **EXISTS** | STA-20 migrations + rag routers |

**Remaining gap:** Monitor cross-encoder model load failures in prod (`cross_encoder_load_failed` fallback in logs).

---

## 5. Conversation

| Item | Status | File:line |
|------|--------|-----------|
| Conversations schema | **EXISTS** | `supabase/migrations/20260604120000_assistant_conversations.sql` |
| CRUD + archive + bulk delete | **WIRED** | `conversations.py`; web proxies |
| Assistant chat `conversation_id` | **WIRED** | `assistant.py:735` |
| Message persistence | **WIRED** | `assistant.py:336` (`persist` helpers) |
| Sidebar groups (F4) | **WIRED** | `apps/web/app/assistant/page.tsx` + `conversation-sidebar.tsx` |
| User intelligence / preferences | **WIRED** | `user_intelligence.py`; `/api/assistant/preferences` |
| Org context pill (F4) | **WIRED** | `org-context-pill.tsx`; `assistant.py:826` (`/org-context`) |

**Remaining gap:** None blocking production.

---

## 6. Integrations as tools

| Item | Status | File:line |
|------|--------|-----------|
| Unified `invoke_tool` | **EXISTS · WIRED** | `tool_service.py:2477` |
| Connector rate limits | **EXISTS** | `connectors/rate_limit.py` |
| Workflow step → tool mapping | **WIRED** | `tool_service.py:2748` (`params_for_step`) |
| ReAct → tool registry | **WIRED** | `react_engine.py` via `ToolRegistry` |
| OAuth connector catalog | **WIRED** | Connectors router + `/api/connectors/*` proxies |
| CS integration health scan | **WIRED** | Smoke `integration_health: score=96` |

**Remaining gap:** Not every connector vendor has workflow step handlers — see connector production readiness docs.

---

## 7. Frontend wiring (Epic I + F1–F4)

| UI surface | Linear | Status | Key path |
|------------|--------|--------|----------|
| Meson wizard | STA-164 | **WIRED** | `components/gravitre/meson-wizard.tsx` |
| Agent chat | STA-163 | **WIRED** | `app/agents/[id]/chat/page.tsx` |
| Assign task | STA-165 | **WIRED** | `app/assignments/new/page.tsx` |
| Workflow run/preview | STA-166 | **WIRED** | `app/workflows/[id]/builder/page.tsx` |
| CS command center | STA-167 | **WIRED** | `components/enterprise/cs-dashboard-tab.tsx` |
| Role pack install | STA-168 | **WIRED** | `app/marketplace/role-packs/page.tsx` |
| Federation | STA-169 | **WIRED** | `app/settings/federation/page.tsx` |
| Run interrupt | STA-170 | **WIRED** | `app/runs/[id]/page.tsx` |
| Meson copilot panel | STA-149 | **WIRED** | `components/workflows/meson-copilot-panel.tsx` |
| Agent intelligence cards | STA-152 | **WIRED** | `app/agents/page.tsx` |
| Run execution timeline | STA-153 | **WIRED** | `components/runs/execution-timeline.tsx` |
| Assistant intelligence | STA-154 | **WIRED** | `app/assistant/page.tsx` |
| Enterprise assistant upgrade | STA-156 | **WIRED** | Sidebar, tools, follow-ups, models |

---

## 8. Missing or deferred endpoints

| Endpoint / capability | Status | Notes |
|----------------------|--------|-------|
| `GET /api/agents` → `knowledgeDocCount` | **MISSING** | F2 uses client-side fallback |
| `POST /api/runs/{id}/steps/{stepId}/retry` | **MISSING** | Full-run retry only |
| `POST /api/runs/{id}/resume` (from paused) | **MISSING** | Pause exists; resume UX open |
| `GET /api/meson/optimizations/{workflowId}` | **MISSING** | Insights used instead (`/insights`) |
| True provider streaming edge cases (STA-5) | **PARTIAL** | `prepare_stream` + `stream` shipped; STA-5 can close |

---

## 9. Production verification

| Check | Command / artifact | Result (2026-06-13) |
|-------|-------------------|---------------------|
| Backend pytest | `cd backend && python -m pytest -q` | 803 passed |
| Frontend typecheck + build | `cd apps/web && npx tsc --noEmit && npm run build` | Pass |
| Prod smoke | `npm run smoke:ai-production:report` | 15 pass / 0 warn / 0 fail |
| Vercel deploy | `c768f28` on `main` | Build OK |
| Railway backend | Auto-deploy from `main` | Smoke target 200 |

---

## 10. Recommended follow-ups (post-8/10)

1. **Agent API:** Add `knowledgeDocCount` (or link to training datasets) on `/api/agents` — remove F2 mock (`agents/page.tsx:83`).
2. **Workflow ops:** Per-step retry + resume-from-paused run actions.
3. **Meson:** Wire optimization “Apply” to a concrete workflow mutation or builder action.
4. **STA-5:** Close Linear issue — token streaming path exists; verify edge-case failover and mark Done.
5. **Re-run smoke** after each epic ships; append results to `smoke-ai-production-latest.json`.

---

## Appendix — Related deliverables

```text
docs/delivery/GRAVITRE_AI_INTELLIGENCE_UPGRADE.md   # Phase 1–2 audit (STA-155)
docs/delivery/STA-156_PHASE5_VERIFICATION.md        # pytest + smoke scores
docs/delivery/smoke-ai-production-latest.json       # latest prod E2E
docs/design/V0_AI_INTELLIGENCE_PROMPTS.md           # F1–F4 spec
docs/delivery/AI_ML_OPERATIONAL_GAP_REPORT.md       # superseded Jun 7 snapshot
```

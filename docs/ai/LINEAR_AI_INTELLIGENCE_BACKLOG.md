# Linear AI Intelligence Backlog (Cursor reference)

Use this file to navigate the **AI Intelligence Upgrade** in Cursor. Issues live in [Linear — Staqbot](https://linear.app/staqbot).

| Wave | Horizon | Project | Initiative |
|------|---------|---------|------------|
| **AI** | 6 months | [AI Intelligence Platform](https://linear.app/staqbot/project/ai-intelligence-platform-67c36b17ace8) | AI Intelligence Upgrade — Gravitre Operating Model |

**Re-run issue creation:** `npm run linear:ai-intelligence` (requires `LINEAR_API_KEY` — idempotent re-run may duplicate; use existing IDs below).

**Spec & audit:** [`docs/delivery/GRAVITRE_AI_INTELLIGENCE_UPGRADE.md`](../delivery/GRAVITRE_AI_INTELLIGENCE_UPGRADE.md)

**v0 prompts (F1–F4):** [`docs/design/V0_AI_INTELLIGENCE_PROMPTS.md`](../design/V0_AI_INTELLIGENCE_PROMPTS.md)

**Production readiness spec:** IMPL 1–10 in AI/ML integration prompt (backend wiring, not UI redesign)

**Issue IDs JSON:** [`docs/ai/ai-intelligence-linear-ids.json`](ai-intelligence-linear-ids.json)

---

## How to work through this in Cursor

1. Open this file with **@LINEAR_AI_INTELLIGENCE_BACKLOG.md**.
2. Pick the next issue in **Recommended order** whose dependencies are done.
3. Say: *"Implement STA-XX — [title]"* and reference the issue description in Linear.
4. Mark done in Linear when merged.

**Frontend (F1–F4):** Implement in **v0.dev**, not Cursor. Merge to `main` preserving backend (same process as v0 P1–P7 merge).

---

## Epics

| Epic | Linear | Focus |
|------|--------|--------|
| A Agent Intelligence | [STA-126](https://linear.app/staqbot/issue/STA-126) | AgentIntelligence, ReAct, role prompts, RAG per task |
| B Workflow Execution | [STA-127](https://linear.app/staqbot/issue/STA-127) | Graph engine, parallel batches, approval gates, logs |
| C Meson Copilot | [STA-130](https://linear.app/staqbot/issue/STA-130) | MesonService, `/api/meson/*`, preferences, feedback |
| D Assistant & Org Context | [STA-128](https://linear.app/staqbot/issue/STA-128) | Conversations, org context, tools, true streaming |
| E Enhanced RAG | [STA-129](https://linear.app/staqbot/issue/STA-129) | Cross-encoder + BM25 hybrid reranking |
| F v0 Intelligence UI | [STA-132](https://linear.app/staqbot/issue/STA-132) | F1 Meson panel, F2 agent cards, F3 run timeline, F4 assistant |
| G Discovery & Verification | [STA-131](https://linear.app/staqbot/issue/STA-131) | Audit deliverable, gap report, smoke tests |
| H Integration Tool Registry | [STA-157](https://linear.app/staqbot/issue/STA-157) | ToolRegistry + ReAct → invoke_tool (IMPL 4) |
| I Production E2E Wiring | [STA-158](https://linear.app/staqbot/issue/STA-158) | Meson wizard, agent chat, buttons → backend (IMPL 7–8) |

---

## Issues — recommended execution order (backend + wiring)

| Order | Ref | Linear | Title | Blocked by |
|-------|-----|--------|-------|------------|
| 0 | AI-023 | [STA-155](https://linear.app/staqbot/issue/STA-155) | Phase 1–2 discovery deliverable ✅ | — |
| 1 | AI-015 | [STA-147](https://linear.app/staqbot/issue/STA-147) | OrgContextService | — |
| 2 | AI-013 | [STA-145](https://linear.app/staqbot/issue/STA-145) | Wire assistant chat to conversations | — |
| 3 | AI-017 | [STA-151](https://linear.app/staqbot/issue/STA-151) | True token streaming | STA-145 |
| 4 | AI-025 | [STA-159](https://linear.app/staqbot/issue/STA-159) | ToolRegistry — integration tools | STA-10, STA-11 |
| 5 | AI-001 | [STA-137](https://linear.app/staqbot/issue/STA-137) | Universal AgentIntelligence layer | STA-20, STA-17, STA-159 |
| 6 | AI-040 | [STA-174](https://linear.app/staqbot/issue/STA-174) | AGENT_PERSONAS + revenue_ops | STA-137 |
| 7 | AI-002 | [STA-138](https://linear.app/staqbot/issue/STA-138) | Role-specific agent prompts | STA-137 |
| 8 | AI-003 | [STA-133](https://linear.app/staqbot/issue/STA-133) | ReAct reasoning engine | STA-137, STA-159 |
| 9 | AI-026 | [STA-160](https://linear.app/staqbot/issue/STA-160) | ReAct → invoke_tool wiring | STA-133, STA-159 |
| 10 | AI-004 | [STA-134](https://linear.app/staqbot/issue/STA-134) | Wire RAG into every agent task | STA-137, STA-20 |
| 11 | AI-031 | [STA-165](https://linear.app/staqbot/issue/STA-165) | Wire Assign Task → agent-jobs | STA-133 |
| 12 | AI-030 | [STA-163](https://linear.app/staqbot/issue/STA-163) | Agent-scoped chat + /agents/[id]/chat | STA-137, STA-174 |
| 13 | AI-005 | [STA-135](https://linear.app/staqbot/issue/STA-135) | WorkflowExecutionEngine | STA-19, STA-12 |
| 14 | AI-006–008 | STA-140, STA-139, STA-136 | Parallel, approval, logs | STA-135 |
| 15 | AI-032 | [STA-166](https://linear.app/staqbot/issue/STA-166) | Wire Run/Preview → execute/dry-run | STA-135, STA-120 |
| 16 | AI-009 | [STA-141](https://linear.app/staqbot/issue/STA-141) | MesonService core | STA-122, STA-123 |
| 17 | AI-027 | [STA-161](https://linear.app/staqbot/issue/STA-161) | Meson interpret + /api/meson/interpret | STA-141, STA-147 |
| 18 | AI-010 | [STA-142](https://linear.app/staqbot/issue/STA-142) | Meson API router (incl. interpret) | STA-141 |
| 19 | AI-028 | [STA-162](https://linear.app/staqbot/issue/STA-162) | Next.js /api/meson/* proxies | STA-142 |
| 20 | AI-029 | [STA-164](https://linear.app/staqbot/issue/STA-164) | Wire MesonWizard → backend | STA-161, STA-162 |
| 21 | AI-011–012 | STA-143, STA-144 | Meson prefs + feedback | STA-142 |
| 22 | AI-016 | [STA-148](https://linear.app/staqbot/issue/STA-148) | Expanded assistant tools | STA-147, STA-10 |
| 23 | AI-014 | [STA-146](https://linear.app/staqbot/issue/STA-146) | Conversation summarization | STA-145 |
| 24 | AI-018 | [STA-150](https://linear.app/staqbot/issue/STA-150) | Cross-encoder + BM25 RAG | STA-20 |
| 25 | AI-037 | [STA-171](https://linear.app/staqbot/issue/STA-171) | Semantic chunking in ingest | STA-20 |
| 26 | AI-033 | [STA-167](https://linear.app/staqbot/issue/STA-167) | CS Command Center → live APIs | STA-124 |
| 27 | AI-034 | [STA-168](https://linear.app/staqbot/issue/STA-168) | Role pack install E2E | STA-121 |
| 28 | AI-035 | [STA-169](https://linear.app/staqbot/issue/STA-169) | Federation invite E2E | STA-116 |
| 29 | AI-036 | [STA-170](https://linear.app/staqbot/issue/STA-170) | Run interrupt/rollback wiring | STA-108, AI-021 |
| 30 | AI-019–022 | STA-149–154 | v0 F1–F4 UI (v0.dev) | backend deps above |
| 31 | AI-038 | [STA-172](https://linear.app/staqbot/issue/STA-172) | AI/ML Operational Gap Report | ongoing |
| 32 | AI-039 | [STA-173](https://linear.app/staqbot/issue/STA-173) | smoke:ai-production E2E | AI-001–036 |
| 33 | AI-024 | [STA-156](https://linear.app/staqbot/issue/STA-156) | Phase 5 pytest + smoke (superseded by AI-039) | AI-039 |

---

## Production wiring checklist (IMPL 8)

| UI action | Linear | Status today |
|-----------|--------|--------------|
| Build with Meson | [STA-164](https://linear.app/staqbot/issue/STA-164) | Mock in `meson-wizard.tsx` |
| Chat with Agent | [STA-163](https://linear.app/staqbot/issue/STA-163) | Page exists; uses mockAgent |
| Assign Task | [STA-165](https://linear.app/staqbot/issue/STA-165) | Proxy exists; UI may be placeholder |
| Workflow Run/Preview | [STA-166](https://linear.app/staqbot/issue/STA-166) | API client exists; builder wiring TBD |
| CS Scan | [STA-167](https://linear.app/staqbot/issue/STA-167) | Dashboard UI; load errors in prod |
| Role pack Install | [STA-168](https://linear.app/staqbot/issue/STA-168) | API client exists |
| Federation Invite | [STA-169](https://linear.app/staqbot/issue/STA-169) | Dialog wired; verify E2E |
| Run Interrupt | [STA-170](https://linear.app/staqbot/issue/STA-170) | Backend STA-108; UI TBD |

---

## Score targets

| Dimension | Before | Target |
|-----------|--------|--------|
| Agent intelligence | 4/10 | 8/10 |
| Workflow execution | 6/10 | 8/10 |
| Meson intelligence | 2/10 | 7/10 |
| RAG quality | 6/10 | 8/10 |
| Assistant | 5/10 | 9/10 |
| Streaming | 3/10 | 8/10 |
| Cross-agent collaboration | 6/10 | 8/10 |
| **Overall** | **4.5/10** | **8/10** |

---

## Relationship to Tier 5

| Tier 5 | AI Upgrade |
|--------|------------|
| [STA-120](https://linear.app/staqbot/issue/STA-120) Digital twin | B2 simulation + F3 run monitor |
| [STA-122](https://linear.app/staqbot/issue/STA-122) Failure prediction | Meson anomalies (STA-141) |
| [STA-123](https://linear.app/staqbot/issue/STA-123) Auto-suggest | Meson suggestions (STA-141) |
| [STA-116](https://linear.app/staqbot/issue/STA-116) B2B handoff | AgentIntelligence handoff (STA-137) |
| [STA-17](https://linear.app/staqbot/issue/STA-17) Handoff bus | ReAct + agent prompts (STA-133–134) |

---

## Key code paths

| Area | Path |
|------|------|
| Agent jobs (today) | `backend/app/operators/agent_jobs.py` |
| Handoffs | `backend/app/services/handoff_service.py` |
| Workflow execute | `backend/app/workflows/execute.py` |
| Graph compile | `backend/app/workflows/builder_sync.py` |
| Assistant | `backend/app/routers/assistant.py` |
| Conversations API | `backend/app/routers/conversations.py` |
| RAG | `backend/app/services/rag_service.py` |
| Meson wizard UI | `apps/web/components/gravitre/meson-wizard.tsx` |
| v0 prompts | `docs/design/V0_AI_INTELLIGENCE_PROMPTS.md` |

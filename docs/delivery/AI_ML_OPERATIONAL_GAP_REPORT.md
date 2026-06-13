# AI/ML Operational Gap Report — STA-172

> **Superseded (2026-06-13):** Use [`GRAVITRE_AI_ML_PRODUCTION_READINESS.md`](GRAVITRE_AI_ML_PRODUCTION_READINESS.md) for current EXISTS/MISSING/WIRED status. This file retains the June 7 Epic I snapshot for history.

**Date:** 2026-06-07  
**Parent epic:** [STA-131](https://linear.app/staqbot/issue/STA-131) Discovery & Verification  
**Linear:** [STA-172](https://linear.app/staqbot/issue/STA-172)  
**Prior audit:** [`GRAVITRE_AI_INTELLIGENCE_UPGRADE.md`](GRAVITRE_AI_INTELLIGENCE_UPGRADE.md) (STA-155, Phase 1–2)

This report closes the **production E2E wiring** slice (Epic I, STA-158) and records what still blocks an **8/10** operational AI/ML posture. It is the input checklist for [STA-173](https://linear.app/staqbot/issue/STA-173) (`smoke:ai-production`).

---

## Executive summary

| Area | Status | Notes |
|------|--------|-------|
| **Epic I — Production E2E wiring** | **Prod smoke run** | STA-173 `smoke:ai-production` passed 2026-06-12 (12 pass / 3 warn) — see `docs/delivery/smoke-ai-production-latest.json` |
| **STA-171 — Semantic RAG chunking** | **Shipped** | Default `semantic` strategy in ingest + worker |
| **AI governance** (router, guardrails, billing, audit) | **Strong** | Unchanged from STA-155 |
| **Unified intelligence layer** (ReAct, personas, streaming) | **Open** | STA-137–174 backlog |
| **Backend tests** | **679 passed** | Local run 2026-06-07 |

**Verdict:** Platform **operations wiring** for the IMPL 8 button checklist is largely done in code. **Intelligence depth** (ReAct, true streaming, cross-encoder RAG, graph-native execution) remains the main gap to the 8/10 target.

---

## IMPL 8 — Production wiring checklist (updated)

| UI action | Linear | Code status | Prod verified | Key paths |
|-----------|--------|-------------|---------------|-----------|
| Build with Meson | STA-164 | **Wired** — `mesonApi.interpret` / `deploy` | ☑ | `apps/web/components/gravitre/meson-wizard.tsx`, `/api/meson/*` |
| Chat with Agent | STA-163 | **Wired** — agent-scoped chat transport | ☑ | `apps/web/app/agents/[id]/chat/page.tsx` |
| Assign Task | STA-165 | **Wired** — `useAsyncJob` → `/api/agent-jobs` | ☑ | `apps/web/app/assignments/new/page.tsx`, `hooks/use-async-job.ts` |
| Workflow Run/Preview | STA-166 | **Wired** — execute + poll + dry-run drawer | ☑ (execute warn: approve 500) | `apps/web/app/workflows/[id]/builder/page.tsx`, `lib/workflows/run-monitor.ts` |
| CS Command Center | STA-167 | **Wired** — scan + health + error/retry UI | ☑ | `components/enterprise/cs-dashboard-tab.tsx`, `POST …/failure-predictions/scan` |
| Role pack Install | STA-168 | **Wired** — install guard + deep links | ☑ | `apps/web/app/marketplace/role-packs/page.tsx` |
| Federation Invite | STA-169 | **Wired** — consent UI + handoff create | ☑ | `apps/web/app/settings/federation/page.tsx` |
| Run Interrupt | STA-170 | **Wired** — pause/cancel via STA-108 | ☑ (rollback warn: HTTP 500) | `apps/web/app/runs/[id]/page.tsx`, builder execution HUD |

**Legend:** Prod verified via `npm run smoke:ai-production:report` against Railway (`2026-06-12`). Warnings = partial backend gaps (approve path, rollback route, Meson copilot APIs).

---

## Epic I deliverables (STA-166 – STA-170)

### STA-166 — Workflow Run/Preview

| Item | Status |
|------|--------|
| `executeWorkflow()` → `run_id` + inline steps | ✅ |
| Live polling via `runsApi.getWithSteps` | ✅ |
| Dry-run prefetched in intelligence drawer | ✅ |
| `/api/runs/[id]` proxies to FastAPI | ✅ |

**Remaining gap:** Long-running runs depend on poll timeout (120s default); no resume-from-paused UX.

### STA-167 — CS Command Center

| Item | Status |
|------|--------|
| Org-wide `POST /api/workflows/failure-predictions/scan` | ✅ |
| Missing-table fallbacks on health/suggestions | ✅ |
| Dashboard error banner + Retry + Scan button | ✅ |

**Remaining gap:** Prod requires migrations for integration health tables; verify on deploy.

### STA-168 — Role pack install E2E

| Item | Status |
|------|--------|
| Connector readiness guard (409) | ✅ |
| Post-install links + `?pack=` deep link | ✅ |
| CS suggestion links to marketplace | ✅ |

**Remaining gap:** Prod smoke with real connector catalog state.

### STA-169 — Federation invite E2E

| Item | Status |
|------|--------|
| `{ partnership }` / `{ handoff }` response wrappers | ✅ |
| `pending_partner` / `pending_receiver` status alignment | ✅ |
| `currentOrgId` + consent logic | ✅ |
| Admin-gated invite + UUID validation | ✅ |

**Remaining gap:** Cross-org handoff create UI shipped (STA-169); prod smoke lists partnerships/handoffs (empty org OK).

### STA-170 — Run interrupt UI

| Item | Status |
|------|--------|
| `POST /api/runs/{id}/pause` + interrupt-aware cancel | ✅ |
| Run detail Pause/Cancel + polling while `running` | ✅ |
| Builder HUD Pause/Cancel during execute poll | ✅ |
| `agentInterruptsApi` + `runsApi.pause/cancel` | ✅ |

**Remaining gap:** Rollback still separate path; no resume-from-`paused` workflow run action.

---

## STA-171 — Semantic RAG chunking

| Item | Status |
|------|--------|
| `chunk_text_semantic()` — paragraph/sentence boundaries | ✅ |
| `chunking.strategy`: `semantic` (default) \| `fixed` | ✅ |
| Worker + `RAGService.ingest_document` use shared API | ✅ |
| Tests `tests/rag/test_chunk_text.py` | ✅ 6/6 |

**Remaining gap:** Cross-encoder rerank (STA-150) still open; semantic chunking alone does not reach 8/10 RAG score.

---

## Operational gaps by dimension

Scores vs [STA-155 baseline → target](GRAVITRE_AI_INTELLIGENCE_UPGRADE.md#score-targets).

| Dimension | Before (STA-155) | After Epic I + STA-171 | Target | Top remaining gap |
|-----------|------------------|------------------------|--------|-------------------|
| Agent intelligence | 4/10 | **4/10** | 8/10 | No ReAct / `AgentIntelligence` (STA-137) |
| Workflow execution | 6/10 | **7/10** | 8/10 | Sequential runtime; no graph batches (STA-135) |
| Meson intelligence | 2/10 | **5/10** | 7/10 | Interpret/deploy wired; no proactive suggestions API (STA-141) |
| RAG quality | 6/10 | **6.5/10** | 8/10 | Semantic chunk ✅; cross-encoder rerank open (STA-150) |
| Assistant | 5/10 | **5/10** | 9/10 | Pseudo-stream; chat persistence partial (STA-145/151) |
| Streaming | 3/10 | **3/10** | 8/10 | Token streaming not implemented (STA-151) |
| Cross-agent collaboration | 6/10 | **7/10** | 8/10 | Federation E2E UI ✅; universal handoff on all agents open |
| **Overall** | **4.5/10** | **5.5/10** | **8/10** | Intelligence layer + prod smoke |

---

## P0 — Block prod smoke (STA-173)

1. ~~Deploy Epic I changes to Railway + Vercel~~ — deployed on `main` through `d165232`.
2. ~~Run `npm run smoke:ai-production:report`~~ — **2026-06-12:** 12 pass / 3 warn / 0 fail (`docs/delivery/smoke-ai-production-latest.json`).
3. **Follow-up fixes from smoke warnings:**
   - `POST /api/approvals/{run_id}/approve` → HTTP 500 on production (blocks full ABC execute completion).
   - `POST /api/runs/{id}/rollback` → HTTP 500 on missing run (route wiring OK; handler error).
   - Meson copilot backend routes (`/api/meson/suggestions|alerts|insights`) → 404 until STA-142.
4. **Agent detail page** (`/agents/[id]`) still uses `mockAgent` for non-chat tabs — does not block chat but blocks trustworthy agent ops UI.

---

## P1 — High-value intelligence gaps (post-wiring)

| ID | Gap | Linear |
|----|-----|--------|
| G1 | Universal `AgentIntelligence` + ReAct loop | STA-137, STA-133, STA-160 |
| G2 | Role personas (`AGENT_PERSONAS`, revenue_ops) | STA-174, STA-138 |
| G3 | True assistant token streaming | STA-151 |
| G4 | Assistant ↔ conversations persistence | STA-145 |
| G5 | Graph-native `WorkflowExecutionEngine` | STA-135 |
| G6 | Cross-encoder + BM25 hybrid rerank | STA-150 |

---

## P2 — UX / polish

| ID | Gap |
|----|-----|
| U1 | Agent list/detail live metrics (replace mock performance data) |
| U2 | Workflow run **resume** after `paused` interrupt |
| U3 | v0 F1–F4 panels (Meson copilot, run timeline, assistant sidebar) — [`V0_AI_INTELLIGENCE_PROMPTS.md`](../design/V0_AI_INTELLIGENCE_PROMPTS.md) |

---

## Verification snapshot (2026-06-07)

| Suite | Result |
|-------|--------|
| `pytest` (backend) | **679 passed** |
| `tests/rag/test_chunk_text.py` | 6 passed |
| `tests/services/test_b2b_handoff_service.py` | 7 passed |
| `tests/services/test_agent_interrupt_service.py` | (included in full suite) |
| Web `tsc` / build | Not re-run this session — run before deploy |
| Prod IMPL 8 smoke | **Run 2026-06-12** — `smoke:ai-production:report` (12 pass / 3 warn) |

---

## Recommended order (after this report)

1. **Fix prod smoke warnings** — approve-run HTTP 500, rollback handler 500, then re-run `smoke:ai-production:report`.
2. **STA-142** — Meson copilot backend (`/api/meson/suggestions|alerts|insights|feedback`) so copilot proxies return 200.
3. **STA-174** — `AGENT_PERSONAS` + `revenue_ops` (unblocks richer agent chat + ReAct trace in jobs).
4. **STA-151** — True streaming (user-visible assistant win).
5. **STA-137 / STA-133** — AgentIntelligence + ReAct with tool trace in prod smoke.
6. **STA-150** — Cross-encoder RAG (pairs with STA-171 chunking).

---

## Appendix — Reference files

```text
Epic I wiring
  apps/web/lib/workflows/run-monitor.ts
  apps/web/app/workflows/[id]/builder/page.tsx
  apps/web/components/enterprise/cs-dashboard-tab.tsx
  apps/web/app/marketplace/role-packs/page.tsx
  apps/web/app/settings/federation/page.tsx
  apps/web/app/runs/[id]/page.tsx

Interrupt (STA-108/170)
  backend/app/services/agent_interrupt_service.py
  backend/app/routers/workflows.py  (runs pause/cancel)

Semantic chunking (STA-171)
  backend/app/rag/ingest.py
  backend/app/rag/worker.py

Prior audit
  docs/delivery/GRAVITRE_AI_INTELLIGENCE_UPGRADE.md
```

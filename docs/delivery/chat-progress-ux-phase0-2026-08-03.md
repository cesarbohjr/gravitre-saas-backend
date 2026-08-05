# Chat progress UX — Phase 0 audit (2026-08-03)

Canvas: `canvases/chat-progress-ux-phase0-audit.canvas.tsx`

## Findings

### 1. Plan-bar / SSE granularity — GENERIC today
Streaming `ResearchPlanPanel` shows stage templates (`Routing tier: research`, `Preparing tools for Apollo`). Named labels already exist on approve plans (`Create contact list`) and tool chips — unused by the streaming bar.

### 2. BusinessOutcome artifact card — YES, already works
`BusinessOutcomeView` (`density=chat`) renders summary + vendor/Gravitre evidence links from Module A. No rebuild for v1.

### 3. File-type outputs — durable hosted files (Phase 2 BUILT 2026-08-03)
`generate_document` now persists md/docx/pdf/html (+ csv when a markdown table is present) via `chat_hosted_file_service`. File-reference chips + Preview/Code pane ship in chat tool results / execution panel. See `docs/delivery/output-preview-fidelity-2026-08-03.md`.

### 4. Step-count telemetry (prod, 45d)
Source: `workflow_runs` where `parameters.source` / `definition_snapshot.source` ∈ `chat_orchestration` | `assistant_chat`.

| Cohort | n | ≤2 steps | ≥3 | ≥4 |
|--------|---|----------|----|-----|
| all_chat_sourced | 205 | 99.5% | 0.5% | 0.5% |
| chat_with_recorded_steps | 25 | 96.0% | 4.0% | 4.0% |
| chat_orchestration_only | 16 | 93.8% | 6.3% | 6.3% |

Recorded-steps histogram: 1→16, 2→8, 3→0, 4–6→1, 7+→0.

## v2 panel threshold (evidence-based)
**Auto-show side panel when planned/executed step count ≥ 3.**

Rationale: clear gap between 1–2 step majority (96% of recorded chat tasks) and the 4+ multi-step tail; zero observations at exactly 3.

## Ship (code)

| Piece | Location |
|-------|----------|
| Named `Running:` / `Completed:` labels (v1) | `agent_platform_optimizer.format_live_progress_label` + SSE `progressSteps` |
| Threshold helper | `apps/web/lib/task-side-panel-threshold.ts` (`SIDE_PANEL_STEP_THRESHOLD = 3`) |
| Side panel Progress / Outputs / Context (v2) | `apps/web/components/gravitre/assistant/task-side-panel.tsx` |
| Wire-up | `apps/web/app/ai/_components/ai-workspace.tsx` |
| Feature commit | `1fea14ff` |

## Live verification append (v1 + v2)

Script: `scripts/verify-chat-progress-ux-v2-live.py`  
Artifact: `docs/delivery/chat-progress-ux-v2-live.json`  
UI harness: `/e2e/task-side-panel?mode=on|off` + `e2e/task-side-panel.spec.ts`  
Screenshot: `docs/delivery/_artifacts/task-side-panel-harness.png`

| Check | Expected |
|-------|----------|
| Tip includes `1fea14ff` | `/health` `git_sha` ancestor |
| Under-threshold chat | `show_panel=false` (inline-only) |
| Multi-step chat (≥3 named/pending steps) | `show_panel=true` + named labels not stage-template generic |
| Outputs identity | Panel list = `GET /api/business-outcomes` filtered by `conversationId` |
| UI harness on/off | Playwright PASS |

### Live evidence (2026-08-04)

Artifact: `docs/delivery/chat-progress-ux-v2-live.json` — **overall PASS**

| Check | Result | Evidence |
|-------|--------|----------|
| Tip | **PASS** | `/health` `git_sha=45b013b8…` @ `2026-08-04T21:48:50Z` (includes `1fea14ff`; Railway + Vercel success) |
| Under-threshold | **PASS** | convo `fd168be6-…` · `step_count=0` · `show_panel=false` |
| Multi-step ≥3 | **PASS** | seeded orch convo `a9f2cc84-…` · state `awaiting_plan_confirm` · steps Create/Search/Add · `show_panel=true` |
| Named labels | **PASS** | `Step 1/3: Create contact list` … (not stage-template generic) |
| Outputs filter identity | **PASS** | `GET /api/business-outcomes` filter by `conversationId` (sample `3e0d1b83-…` → 1 row) |
| Isolated org | | `f07e57c0-…` / user `a9f1240f-…` |
| UI harness | **PASS** | Playwright `e2e/task-side-panel.spec.ts` (on + off) · `docs/delivery/_artifacts/task-side-panel-harness.png` |

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

# Canvas edge program — Phases 0–5 (2026-07-25)

Standing rules unchanged: no write path outside `catalog_write_authority`; no confidence without Module C `label_confidence`; no parallel BusinessOutcome store for canvas.

## Phase 0 — Current state (confirmed before build)

| # | Question | Verdict |
|---|----------|---------|
| 1 | Canvas writes → catalog_write_authority | **PARTIAL → closed for agent path** — invoke_tool / slack / email / webhook already gated; agent steps now honor `workflow_runs` approval via `react_engine` + `canvas_write_gate` |
| 2 | Results via BusinessOutcome | **PARTIAL** — run-level BusinessOutcomeView + per-node raw step output (unchanged; no duplicate DTO) |
| 3 | Canvas → Module B / chat memory | **GAP → wired** — Module A `intelligence_outcome_events` injected into chat orchestrator; `record_action_outcome` when `conversation_id` present |
| 4 | Meson edit existing canvas | **GAP → built** — `POST /api/meson/edit` + apply + reviewable structural diff |

## Phase 1 — Governance-native

- Backend: canvas agent writes use run-level approval when `ToolContext.run_id` resolves to `workflow_runs`.
- UI: connector/tool write nodes show chat-parity **needs approval** badge (`write-authority.ts` framing; SoT remains backend).

## Phase 2 — Conversational canvas editing

- `POST /api/meson/edit` → proposal + `definition_diff` (BusinessOutcome-style prior/summary).
- `POST /api/meson/edit/apply` → `sync_builder_graph` (versioned save).
- Meson panel: NL instruction → reviewable diff → Apply.
- Session proposal history: `GET /api/meson/edit/history/{workflowId}` (undo foundation).

## Phase 3 — Shared memory

- `ExecutionMemoryService.recall_recent_workflow_outcomes` reads Module A rows.
- `IntelligenceOrchestrator` injects `<recent_workflow_outcomes>` into prompt.
- `finalize_execution_outcome` mirrors into conversation memory when `conversation_id` in metadata; canvas execute already passes `parameters.source=canvas`.

## Phase 4 — Module C on AI branches

- `DecisionService.evaluate` attaches `label_confidence` fields.
- Decision step output includes reasoning + honesty labels.
- `NodeRunDebugPanel` surfaces Branch reasoning (Module C).

## Phase 5

| # | Item | Status |
|---|------|--------|
| 1 | NL workflow explanation | **Built** — `POST /api/meson/explain/{id}` + Meson Explain button |
| 2 | Per-node reliability signal | **Built** — `GET /api/meson/node-reliability/{id}` + canvas node banner |
| 3 | Cross-workflow failure patterns | **Built** — same endpoint `crossWorkflow` + Meson panel |
| 4 | Governed template sharing (Intelligence Packs) | **Scoped follow-up** — Packs already have install/verify/governance for official packs; arbitrary org↔org canvas marketplace needs new sharing ACL + pack packaging of builder graphs — not in this pass |
| 5 | Undo/rollback from diff history | **Foundation shipped** — proposal history + workflow_versions activate already exist; full revert UI deferred to named follow-up once proposal persistence is durable (today in-process cache) |
| 6 | Sub-workflow / modular canvas | **Scoped follow-up** — execution graph can reference another workflow id as a step conceptually, but nested run isolation / approval inheritance is a larger engine change — separate initiative |

## Live verification checklist (post-deploy)

1. `/health` `git_sha` matches tip.
2. Canvas write node shows **needs approval**; unapproved run blocks with `canvas_write_blocked`.
3. Meson: three sequential NL edits on a saved multi-step canvas, each with reviewable diff.
4. Canvas run → separate chat ask about status; answer cites Module A outcome (not “check Runs”).
5. AI decision node output shows estimated confidence + reasoning.
6. Explain + reliability indicators render without regressions to write authority.

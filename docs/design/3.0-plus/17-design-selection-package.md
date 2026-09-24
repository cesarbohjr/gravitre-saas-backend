# 17 — Phase 6 design-selection package

**Venue:** `/dev/ai-workspace-preview?s=selection` (index)  
**Branch:** `feat/gravitre-3.0-plus-frontend`  
**Authority:** `docs/design/GRAVITRE_3_0_PLUS_MASTER_SPEC.md`  
**Not:** Phase 8 · production builder cutover · core chat edits

## 1. Accessible index

**Primary entry (working prototype, not docs-only):**

`/dev/ai-workspace-preview?s=selection`

On branch `feat/gravitre-3.0-plus-frontend` worktree:

```bash
cd apps/web
pnpm install   # once
pnpm exec next dev --port 3010 --webpack
```

Then open: **http://localhost:3010/dev/ai-workspace-preview?s=selection**

| Area | Primary links |
|------|----------------|
| A Page intro | `?s=page-intro&scene=compare` |
| B Window Manager | `?s=window-manager&scene=docked` · `scene=tour` |
| C Intelligence | `?s=intelligence-journey&scene=field-primary` |
| D React Flow Option B | `?s=workflow-rf&scene=design` · `?s=workflow-gen` |
| E AI workspace | `?s=ai-workspace&scene=split` |
| F Model Studio | `?s=model-studio&scene=standard` |
| §40 Dashboard | `?s=dashboard&scene=attention-first` |
| §40 Agent | `?s=agent-workspace&scene=roster-detail` |

**Screenshots:** open each link above in the browser during review (agent automated capture blocked this session by Next first-compile stalls + isolated browser localhost). Prefer live harness over static shots for interaction/transitions.

Package navigator doc: this file. Status canvas: `gravitre-3.0-plus-section-44.canvas.tsx`.

## 2. Structural options & tradeoffs (summary)

### A — Page intro
| Option | Serve | Tradeoff |
|--------|-------|----------|
| Operating | Dashboard, Activity, Assignments | Actionable; risk of KPI strips |
| Expert | Builder, Model Studio, dense ops | Power density; cold first-run |
| Empty | Insufficient data | Honest; must not default when data exists |
| Immersive | Field/graphs | Canvas primacy; secondary actions harder |

**Cesar decides:** family→pattern map (proposal in compare scene).

### B — Window Manager
| Option | Tradeoff |
|--------|----------|
| **Docked (proposed default)** | Page visible; less immersive |
| Compact | Focused; hides artifact |
| Floating | Flexible; can obscure canvas |
| Expanded / Fullscreen | Deep work; covers page |
| Minimized / Restored | Continuity; needs explicit restore |

Prototype keeps fixture `conversationId` / `taskId` stable across transitions.

**Cesar decides:** production default mode.

### C — Intelligence
| Concept | Tradeoff |
|---------|----------|
| Field-primary | §21 overview; Matrix one click away |
| Matrix rail | Expert always visible; denser / empty cells |
| Split insight | Action strips first; Field demoted |

Journey Insight→Evidence→Relationship→Expert preserved. Empty/insufficient demonstrated.

**Cesar decides:** Field primacy for production chrome.

### D — Option B RF
Demonstrated: Design/Live/Explain/History/ai-preview, node+edge inspect, `canvasToSavePayload`, AI→preview→RF.  
Gaps: Meson apply, decision multi-handles, council UI, version restore API, live `runsApi` overlays.  
**Cesar decides:** cutover only after reviewing `14-option-b-preservation-evidence.md` — not requested now.

### E — AI workspace
Compositions only; show-the-work = placement slot. Runtime = core agent.

### F — Model Studio
Standard vs Advanced progressive disclosure (§22).

## 3. Decisions Cesar must make (checklist)

- [ ] A: Intro pattern map by family  
- [ ] B: WM default mode  
- [ ] C: Intelligence Field primacy yes/no (+ which concept)  
- [ ] D: RF production cutover deferred / approve later  
- [ ] Dashboard §40 concept (optional now)  
- [ ] Agent §40 concept (optional now)  
- [ ] Phase 8 **not** requested from this package alone  

## 4. Phase 6/7 validation

See `16-phase6-validation-notes.md`. Prototype PASS/PARTIAL ≠ authenticated production proof. Phase 7 **not complete**.

## 5. Coverage

`15-coverage-matrix.md` — nested routes expanded (~79 rows). Marketing/api/e2e omitted.

## 6. Core-agent integration dependencies

| Dependency | Owner | Frontend use |
|------------|-------|--------------|
| Conversation / taskState / voice | Core | WM must not remount |
| Artifacts / durable deliverables | Core | AI workspace render |
| Approvals / PendingAction | Core | WM + AI chrome |
| `CanvasWorkflowNode` + getBuilder/saveBuilder | Shared schema | RF visual only |
| execute / dryRun / runsApi | Core | Live overlays later |
| Meson edit/apply | Shared | Gap until RF cutover |
| SSE / chat API | Core | Do not fork |

Hard no-edit: `ai-workspace.tsx`, `chat-execution-panel`, `ai-work-canvas`, `gravitre-command-os`, chat API/SSE.

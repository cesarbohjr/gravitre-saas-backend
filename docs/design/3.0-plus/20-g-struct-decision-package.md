# 20 — G-STRUCT decision package (final for Cesar)

**Date:** 2026-09-24  
**Branch:** `feat/gravitre-3.0-plus-frontend`  
**Authority:** `docs/design/GRAVITRE_3_0_PLUS_MASTER_SPEC.md` §42–48 · gate `G-STRUCT` (`09-implementation-plan-and-release-gates.md`)  
**Harness:** http://127.0.0.1:3010/dev/ai-workspace-preview?s=selection · `?s=g-struct`  
**Purpose of harness:** Structural / interaction validation — **not** finished Gravitre frontend.

**Status:** Package ready for Cesar selection. Broad Phase 8 **blocked** until G-STRUCT is recorded below and Cesar authorizes the first production slice.

---

## How to use this package

1. Decide the **A** items now (enough harness evidence).  
2. Optional: run the **B** focused demos if you want more confidence before selecting.  
3. Leave **C** to Phase 8 / production validation.  
4. Record selections in the signature block.  
5. Authorize **Slice 0** (tokens → primitives → WM shell) only after G-STRUCT.

Do not treat HTTP 200 as Phase 7 complete. Do not treat fixture data as live intelligence / live runs.

---

## A / B / C separation

### A — Select now (harness supports the choice)

| ID | Decision | Options (Cesar picks) | Evidence |
|----|----------|----------------------|----------|
| **A1** | Page-intro **vocabulary** (not one global header) | Approve Operating / Expert / Empty / Immersive as shared families | `?s=page-intro&scene=compare` · SaaSFrame Mintlify operating structure |
| **A2** | Page-family **preliminary map** | Approve map in §4 below (or amend) | Same + coverage matrix `15` |
| **A3** | Window Manager **default policy** | **A:** Contextual default + remembered preference · **B:** Single default (e.g. docked) + explicit switch | `?s=window-manager` modes/tour · stable fixture conversation/task ids |
| **A4** | Intelligence **overview structure** | Field-primary · Matrix rail · Split insight | `?s=intelligence-journey` |
| **A5** | Intelligence **journey principle** | Confirm Insight→Evidence→Relationship→Expert graph preserved | Journey scene + Field-primary evidence cards |
| **A6** | AI workspace **composition direction** | Conversation-primary · Work-primary · Split (runtime stays core) | `?s=ai-workspace` + generation states |
| **A7** | Model Studio **disclosure** | Confirm Standard / Advanced progressive disclosure | `?s=model-studio` |
| **A8** | React Flow Option B | Confirm as **preferred visual-layer direction** — **not** production cutover | `?s=workflow-rf` · `14-option-b-preservation-evidence.md` |
| **A9** | §40 Dashboard / Agent | Optional now: attention-first / ops-board / outcome-rail · roster / workbench / mission | `?s=dashboard` · `?s=agent-workspace` |
| **A10** | Reference hierarchy | Confirm Nodus visual · SaaSFrame structure · SaaSUI enterprise · Mobbin flows · Beautiful UI widgets · 21st.dev after structure | `19-saasframe-research-mapping.md` · `?s=saasframe` |

### B — Focused demos still useful before selection (not broad harness rebuild)

| ID | Demo | Why | Venue |
|----|------|-----|-------|
| **B1** | WM tour across all modes with **stable ids visible** | Confirm continuity contract before choosing A3 | `?s=window-manager&scene=tour` |
| **B2** | Intelligence empty / insufficient | Confirm Empty family honesty | `?s=intelligence-journey&scene=empty` |
| **B3** | RF Design: visible fixture workflow + select node + save payload | Interaction proof of Option B schema/composition (fixture strip + @xyflow layer) | `?s=workflow-rf&scene=design` |
| **B4** | AI generating → complete → needs-approval | Generation-state vocabulary | `?s=ai-workspace&scene=generating` / `complete` / `needs-approval` |
| **B5** | Compact Operating intro | Responsive implication for A1 | `?s=page-intro&scene=operating` + mobile scene if present |

### C — Belong to Phase 8 / production (do not block G-STRUCT)

- Full production page for every route  
- Authenticated Intelligence with live backend  
- Production Workflow Builder cutover (Meson apply, multi-handles, council, version restore, live runsApi)  
- Live chat/SSE/voice execution in production chrome  
- Show-the-work event stream · Visible Computer Use  
- Full keyboard a11y / visual regression / G-PROOF journeys  

---

## 4. Page-family introduction mapping (preliminary)

| Family | Pattern | Typical routes / jobs | Avoid |
|--------|---------|----------------------|--------|
| **Operating** | Title + lead + primary actions + attention/activity (Mintlify-informed; not equal KPI cards) | Dashboard, Activity, Assignments, Approvals, Notifications, Goals list | Decorative card grids |
| **Expert** | Dense meta + tools; canvas/workspace primacy | Workflow Builder, Model Studio, Connector admin, Agent config, Matrix/expert Intelligence | Cold first-run as default |
| **Empty** | Honest insufficient-data + one next action | First-run, no connectors, empty search, insufficient Field data | Fake density |
| **Immersive** | Field/canvas-first chrome | Intelligence Field, Relationship Graph, Knowledge Graph, fullscreen AI work | Hiding secondary actions permanently |

**Cesar:** Approve / amend map. Route-by-route dispositions in `15-coverage-matrix.md` remain binding for Phase 8.

---

## 5. Window Manager default-mode options

| Option | Behavior | Pros | Cons |
|--------|----------|------|------|
| **A — Contextual + remembered preference** | System chooses by page/task/viewport/artifact/voice/approval; user preference wins when set | Matches MSP multitasking; avoids one-size-default | Needs clear policy table in Phase 8 |
| **B — Single default + explicit switch** | e.g. Docked (or Compact) always first; modes always available | Predictable; simpler to ship | Wrong for some tasks/pages |

**Modes preserved:** Compact · Floating · Docked · Expanded · Fullscreen · Minimized · Restored  

**Hard boundary:** WM owns **presentation** only. Conversation / task / artifact / approval / voice **identities** preserved across transitions. **No second runtime.** Core agent owns execution state.

**Cesar:** Pick A or B (and if B, which single default).

---

## 6. Intelligence structural options

| Concept | Structure | Implication |
|---------|-----------|-------------|
| **Field-primary** | Field owns viewport; Matrix/KG one click | Best match to §21 overview-first |
| **Matrix rail** | Expert taxonomy always visible | Denser; empty-cell risk |
| **Split insight** | Insight strip first; Field secondary | Actionable; Field may feel demoted |

**Journey preserved:** Insight → Evidence → Relationship → Expert graph (Field · Matrix · KG · Relationships · Predictive · filters · sources).  

**Harness:** Fixture labeled. **Production:** Real eligible backend state. Fixture ≠ live BI.

**Cesar:** Pick concept (+ confirm journey preservation).

---

## 7. React Flow Option B — production cutover conditions

**Now (G-STRUCT):** Approve Option B as **preferred visual-layer direction** only.

**Not now:** Replace `app/workflows/[id]/builder`.

**Cutover only when all are true (later authorization):**

1. Cesar explicit cutover approval  
2. `CanvasWorkflowNode` + `canvasToSavePayload` / getBuilder·saveBuilder unchanged  
3. Execution, approvals, governance, AI/manual sync preserved  
4. Gaps closed or explicitly deferred with owner:  
   - Meson apply  
   - Decision multi-handles  
   - Council UI  
   - Version restore API  
   - Live runsApi overlays  
5. Golden save/load + execute path evidence (G-PROOF)  
6. Evidence file `14-option-b-preservation-evidence.md` updated with PASS pointers  

**Harness status:** Design mode must show representative fixture graph (visual interaction proof). Schema mapping demonstrated. Gaps remain conceptual until production migration.

---

## 8. Phase 7 validation status

| Layer | Status | Meaning |
|-------|--------|---------|
| **HARNESS VALIDATED** | PARTIAL → ready for G-STRUCT on A-items | Structural concepts visible; RF/AI/WM/intro/Intelligence/Model Studio scenes exist |
| **PRODUCTION INTEGRATION PENDING** | Yes | No production route migration; no authenticated journey PASS |
| **HUMAN ACCEPTANCE PENDING** | Yes | Cesar has not signed G-STRUCT |

| Concern | Harness | Production |
|---------|---------|------------|
| Information hierarchy | HARNESS VALIDATED (page-intro, dashboard, Intelligence) | PENDING |
| User-task comprehension | PARTIAL (fixtures) | PENDING |
| Responsive composition | PARTIAL (compact scenes) | PENDING |
| Keyboard accessibility | NOT RUN | PENDING |
| Window transitions | HARNESS VALIDATED (modes + tour) | PENDING |
| State preservation | PARTIAL (fixture ids in WM) | PENDING (core runtime) |
| Interaction consistency | PARTIAL | PENDING |
| Functional preservation | Documented gaps (RF/Meson/etc.) | PENDING |
| Runtime contracts | Not exercised in harness | Core agent owns |

**Phase 7 is not complete.** It is **ready for Cesar structural selection**. Phase 8 journeys are not required to close Phase 7.

---

## 9. First Phase 8 production slice (ready for authorization after G-STRUCT)

**Do not start until Cesar records G-STRUCT + authorizes Slice 0.**

### Slice 0 — Foundation (master order 1–3)

| Step | Work | Out of scope |
|------|------|--------------|
| 0.1 | Design tokens + typography (Nodus/Gravitre) | New product claims/prices |
| 0.2 | Shared interaction primitives (Button/Input patterns already in design system) | New AI runtime |
| 0.3 | Gravitre Window Manager **presentation shell** wired to existing conversation/task identities | Second chat/SSE; voice execution changes |

**Then (Slice 1, after Slice 0 ships):** AI widgets / chat **presentation** (order 4) → shared drawers/inspectors (5) — still no RF cutover.

**Later slices (ordered, not parallel):** 6 Workflow visual foundation (Option B behind flag) → 7 Dashboard → 8 Agents → 9 Workflows → 10 Intelligence → 11 Model Studio → 12 Connectors/knowledge → 13 Marketplace/goals/assignments/admin → 14 Responsive parity → 15 Visual regression.

Use `01` audit + `15` coverage matrix for dependencies. Isolated worktree until coordinated merge.

---

## 10. Core-agent integration boundaries

| Owner | Owns | Frontend must not |
|-------|------|-------------------|
| **Core product agent** | CognitiveTurnKernel · Cognitive Loop · ExecutionPlan · ActionSpec/HMAC · PendingAction · Observations · Response Composer · Voice runtime · API/SSE · Durable artifacts · Workflow execution · Entity/learning | Fork or remount execution state inside WM/AI chrome |
| **Frontend agent** | Visual architecture · design system · window compositions · presentation · visual interaction · production UI after authorization | Edit core runtime files without coordinated boundary; invent customer prices/badges/Enable |

**Hard no-edit (until coordinated):** `ai-workspace.tsx`, chat-execution-panel, ai-work-canvas, gravitre-command-os, chat API/SSE, production workflow builder, backend execution/governance.

**Show-the-work:** Placement only in designs. Event stream / production UI **later**.  
**Visible Computer Use:** Separate roadmap capability — not complete.

---

## Cesar signature (G-STRUCT)

Record decisions here (or Linear append-only) when selected:

| ID | Cesar selection | Date |
|----|-----------------|------|
| A1 Page vocabulary | ☐ Approve · ☐ Amend: ___ | |
| A2 Family map | ☐ Approve · ☐ Amend: ___ | |
| A3 WM policy | ☐ A Contextual+pref · ☐ B Single default=___ | |
| A4 Intelligence structure | ☐ Field-primary · ☐ Matrix rail · ☐ Split insight | |
| A5 Journey preserved | ☐ Yes | |
| A6 AI composition | ☐ Conversation · ☐ Work · ☐ Split · ☐ Other: ___ | |
| A7 Model Studio Std/Adv | ☐ Yes | |
| A8 RF Option B direction (not cutover) | ☐ Yes · ☐ Hold | |
| A9 §40 Dashboard/Agent | ☐ Skip · ☐ Pick: ___ | |
| A10 Reference hierarchy | ☐ Confirm | |
| **Authorize Slice 0** | ☐ Not yet · ☐ Authorized | |

**Broad Phase 8 and RF production cutover remain separately authorized.**

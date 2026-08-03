# Output preview fidelity — Phase 0 inventory + Phase 1 confirm

Date: 2026-08-03  
Canvas: `canvases/output-preview-fidelity-phase0.canvas.tsx`  
Related: `docs/delivery/chat-progress-ux-phase0-2026-08-03.md`

## Principle

Preview fidelity must match **what is technically renderable** and **what Gravitree actually produces**. Claude’s live Preview/Code pane fits web-native code; Cowork/Manus file chips fit Office blobs. Gravitree’s dominant outputs are **connector writes / BusinessOutcomes** — verified vendor evidence, not generated code or hosted Office files.

## Phase 0 — Real inventory

| Output type | Exists? | Format | Surface | Matched preview |
|-------------|---------|--------|---------|-----------------|
| Connector write BusinessOutcome | **Yes (dominant)** | DTO: summary, evidence links, verification, timeline | Chat `density=chat`, Activity, Runs | Evidence card |
| `generate_document` | Ephemeral only | Markdown in tool payload | Artifact preview text | Not a durable file |
| Artifact registry cards | Yes | Metadata + short preview | Chat fallback when no BO | Link/preview |
| Lite deliverables | Yes (side) | JSON download | `/lite/deliverables` | Download |
| Assignments | Yes (side) | Client `.txt` | Assignments UI | Text + download |
| Admin / metrics CSV | Yes (ops) | CSV | Admin pages | Not assistant output |
| CodeAct | Yes | Text `repr` preview | Artifact report kind | Text only |
| Chat-generated chart / HTML / SVG / React | **No** | — | — | — |
| Dashboard charts | Yes (product UI) | **recharts** | Home / metrics / CS / intelligence | Not task artifacts |
| In-app PDF/DOCX viewer | **No** | — | DOCX is RAG ingest only | — |

## Phase decisions

| Phase | Decision | Rationale |
|-------|----------|-----------|
| **1 Confirm BusinessOutcome** | **DONE — no rebuild** | Already the correct preview for connector outcomes |
| **2 File-reference chip** | **SKIP** | No durable hosted file generation from chat |
| **3 Live Preview/Code** | **SKIP** | No web-renderable chat artifacts; do not add speculative sandbox |

## Phase 1 confirmation (evidence)

### Code path (no change)

- Success + failure: `ChatExecutionPanel` → `BusinessOutcomeView` `density="chat"` when `business_outcome` present  
  (`apps/web/components/gravitre/assistant/chat-execution-panel.tsx`)
- Shared renderer: `apps/web/components/gravitre/business-outcome/business-outcome-view.tsx`  
  (summary, evidence link buttons, verification, timeline)
- Activity: `apps/web/app/activity/page.tsx` (`density="timeline"`)
- Runs: `apps/web/app/runs/[id]/page.tsx`

### Prod data (14d sample)

Runs with `verified_output` (Module A substrate for BO projection), including:

- `50a34d4c-…` — `assistant_chat` / Search contacts / completed / `verified_output` present (2026-08-03)
- `56640bf3-…` — `assistant_chat` / Search contacts / completed / `verified_output` present
- `626aba58-…` — `browser_extension` / completed / `verified_output` present

### Explicit non-goals

- No fake live preview of PDFs or Office files  
- No new charting dependency for chat  
- No speculative file generation just to demo chips  
- Browser extension still uses status text (not BO card) — separate gap, not introduced by this work

## Verification

| Check | Result |
|-------|--------|
| Phase 0 inventory reported before design | PASS — this doc + canvas |
| Phase 1 BO path intact (code) | PASS — early-return to `BusinessOutcomeView` |
| Phase 2 file chip built | N/A — skipped |
| Phase 3 live render built | N/A — skipped |
| Mismatched preview mechanisms added | PASS — none |
| Product code redeploy required | **No** — documentation-only ship |

## Deploy note

No application code changes. Tip deploy confirmation is the currently live Railway `/health` `git_sha` (BusinessOutcome already on tip from prior Module A work). This commit records the fidelity decision only.

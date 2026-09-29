# 07 — React Flow adoption plan

## Current reality

| Canvas | Tech | Path |
|--------|------|------|
| Intelligence Relationships | `@xyflow/react` + dagre | `relationship-graph-canvas.tsx` |
| Intelligence Field / Core map | Custom absolute/SVG layout | `intelligence-graph-stage.tsx`, map topology |
| Workflow builder | **Custom** DOM canvas | `app/workflows/[id]/builder/page.tsx` |
| Schema SoT | `CanvasWorkflowNode` / edges | `lib/workflows/builder-persistence.ts` ↔ API |

## Decision

**Extend** React Flow for **workflow builder visualization**, subject to Cesar approval of the migration. Do **not** create a second workflow definition.

## Migration principles

1. One canonical definition — `canvasToSavePayload` / load remains the bridge  
2. AI (Meson) edits and manual edits converge on the same nodes/edges  
3. No unapproved execution capabilities for the sake of a pretty prototype  
4. Prototype in harness or feature-flagged builder fork — not silent production swap  

## Phased approach

| Phase | Work | Gate |
|-------|------|------|
| RF-0 | Inventory builder node types, edge rules, Meson mutations | Done-ish (this package) |
| RF-1 | Harness: render **read-only** saved workflow via React Flow from `CanvasWorkflowNode` | Cesar visual OK |
| RF-2 | Editable React Flow with same save payload | Contract tests green |
| RF-3 | Cut over production builder behind flag | Live save/run proof |
| RF-4 | Retire custom canvas | No dual renderers |

## Out of scope

- Replacing Intelligence Field custom map with React Flow in this wave (different metaphor)  
- tldraw / ELK unless layout pain is measured after RF-1

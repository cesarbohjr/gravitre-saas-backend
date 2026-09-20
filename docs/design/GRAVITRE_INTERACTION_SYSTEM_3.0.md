# Gravitre Interaction System 3.0

**Status:** Planning — no production rollout authorized  
**Date:** 2026-09-20  
**Companion:** `GRAVITRE_MOTION_SYSTEM.md`, `GRAVITRE_PRODUCT_VISUAL_SYSTEM_3.0_PLUS.md`

---

## Purpose

Define how Gravitre **behaves** — not just how it looks. Interactions communicate runtime state for an AI operations platform.

---

## UI physics (state → behavior)

| State | Behavior |
|-------|----------|
| **Selection** | Focuses; inspector opens; AI context attaches |
| **Connection** | Trace or signal activates between nodes |
| **Execution** | Flow animates along real path (telemetry-bound) |
| **Waiting** | Single subtle breathe on approval/pending |
| **Success** | Resolve mark (`resolve-mark.tsx` pattern) |
| **Failure** | Trace interrupts at stage; no generic toast-only |
| **Learning** | Outcome path returns toward intelligence graph |
| **Expansion** | Preserves spatial origin (AI morph, sheets) |

---

## Interaction catalog

### FOCUS
- Row/graph node click → inspector, not navigation away  
- Keyboard: j/k or arrows in queues (future — prototype on Activity)

### SELECT
- Single selection default; multi where bulk ops exist  
- Clear deselect (Esc, click canvas)

### INSPECT
- **Rule:** no selection → no inspector (Reset 2.0 binding)  
- Inspector = evidence + actions, not duplicate list

### TRACE
- Drill from Activity outcome → stage rail  
- Failed stage pinned; evidence attached to stage  
- Deep link `?trace=1` for experts — also surface in UI for novices

### EXECUTE
- Primary CTA one per context (Approve, Run workflow, Connect)  
- Optimistic UI where safe; governance paths show pending state

### WAIT
- Approval amber semantics; no spinner-only for long holds  
- Copy explains what is blocked

### RESOLVE
- Success closes loop visually (trace complete, resolve mark)  
- Outcome visible before micro-celebration

### FAIL
- Show **where** and **why** — stage + error + retry/fix  
- Ask Gravitre contextual: "Why did this fail?"

### LEARN
- GIBE / learning feedback animates **return** to intelligence (subtle)  
- Not decorative — links to learning hub evidence

### CONNECT
- Connector OAuth: signal from external logo → Gravitre node  
- Post-connect: health indicator, not paragraph of pills

### DELEGATE
- Agent → agent or agent → workflow: edge activation  
- Multi-agent run surfaces delegation chain

### APPROVE
- Queue → inspect → Approve primary  
- On approve: execution **continues** (motion continues trace)

### EXPAND / COLLAPSE
- AI workspace morph (existing `layoutId` path)  
- Rails collapse without losing conversation thread

### SUMMON AI
- One pattern: contextual Ask (selection, error, run)  
- Command palette: "Explain current page"  
- **Not:** Ask button on every toolbar by default

---

## AI movement vocabulary

Represent **one** dominant state per moment:

| Runtime state | User-facing motion |
|---------------|-------------------|
| Listening | Composer waveform (voice) |
| Understanding | Subtle perceive pulse |
| Retrieving | Signal toward source |
| Connecting | Edge draw |
| Planning | Trace stage PLAN highlight |
| Delegating | Edge to agent node |
| Executing | Flow along path |
| Verifying | CHECK stage pulse |
| Learning | Return arc to intelligence |

**Not all at once.**

---

## Motion rules

1. **Inside work, not page transitions** — navigation stays fast  
2. **Data-originated** when possible — workflow run animates real nodes  
3. **Token durations only** — `MOTION.micro|ui|major`, `--g-duration-*`  
4. **Reduced motion** — static equivalents (`MotionConfig`, CSS)  
5. **Quiet vs active screens** — settings calm; activity/workflow active  

---

## Command system 3.0 (interaction layer)

Extend `command-palette.tsx`:

| Command class | Examples |
|---------------|----------|
| Go to… | Routes, recent objects |
| Create… | Agent, workflow, assignment |
| Run… | Workflow, agent task |
| Ask… | Summarize selection, explain failure |
| Find… | Universal search records |
| Connect… | Connector discovery |
| Inspect… | Open inspector on current selection |
| Switch… | Workspace, environment |
| Explain… | Current page purpose (novice aid) |

Keyboard-first for experts; fuzzy discoverable for novices.

---

## Contextual AI affordance

| Intent | Trigger |
|--------|---------|
| Ask about this | Selection chip / context menu |
| Explain this | Inspector footer |
| Fix this | Error state on failed run |
| Summarize this | Activity outcome row |
| Why did this fail? | Trace failure pin |
| What changed? | Intelligence lens |

**Avoid:** duplicate "Ask Gravitre" text buttons on every header — prefer summon icon + command.

---

## Microinteraction audit checklist (for prototype)

- [ ] Button hover/press consistent (`INTERACTION` tokens)  
- [ ] Row hover + selection in tables  
- [ ] Popover/tooltip delay discipline  
- [ ] Toggle/save feedback  
- [ ] Drag workflow node (builder)  
- [ ] Sheet open/close on mobile inspector  

---

## Signature interactions (5–7 candidates)

1. **AI workspace morph** — compact ↔ expanded ↔ fullscreen  
2. **Signal transfer** — connector sync, delegation  
3. **Execution trace** — Activity/run story  
4. **Relationship focus** — graph neighborhood  
5. **Intelligence lens transform** — one topology, many lenses  
6. **Approval → continued execution** — trace resumes  
7. **Outcome → learning return** — GIBE feedback loop  

Prototype all in harness; ship incrementally after Cesar approval.

---

## Novice / expert (one interface)

| Novice | Expert |
|--------|--------|
| Plain labels | Keyboard shortcuts |
| Clear next action | Command palette |
| Progressive disclosure | Dense tables, filters |
| Explain current page | Trace + deep links |

Same routes — no "beginner mode."

---

**STOP:** Implement interactions in prototype harness only until production slice approved.

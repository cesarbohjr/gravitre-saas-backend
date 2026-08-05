# Chat progress UX — v0 visual handoff (2026-08-04)

**Status:** Ready to paste into v0. Functional v1/v2 already shipped (`1fea14ff`); this prompt is **visual + interaction polish** on existing data wiring.  
**Live proof:** `docs/delivery/chat-progress-ux-v2-live.json` — tip-linked PASS.  
**Code today:** `task-side-panel.tsx`, `research-plan-panel.tsx`, `ai-workspace.tsx`, `ai-landing.tsx`, `file-reference-chip.tsx`, `preview-code-pane.tsx`, `business-outcome-view.tsx`.

## How to use

1. Attach the reference screenshots (Cowork side panel, Manus step pills / workspace, Claude Artifacts Preview·Code, Chat vs Cowork dual-mode diagram).
2. Optionally attach a tip screenshot of Gravitre `/ai` with a multi-step task so v0 sees current chrome.
3. Paste the **Paste into v0** block below.
4. Ask v0 for **desktop comps first** (landing + active-task with panel on/off), then a thin mobile pass.
5. Implementation should stay inside `apps/web` Chat surfaces — no new product routes.

## What already works (do not rebuild)

| Capability | Status | Surface |
|------------|--------|---------|
| Named step labels (`Running:` / `Completed:` / `Step N/M:`) | Shipped | SSE → inline plan-bar + panel Progress |
| Side panel auto-show when steps ≥ **3** | Shipped | `SIDE_PANEL_STEP_THRESHOLD` |
| Progress / Outputs / Context sections | Shipped (utilitarian) | `TaskSidePanel` |
| BusinessOutcome evidence card in chat | Shipped | `density="chat"` — keep as inline artifact |
| Hosted file chips + Preview·Code | Shipped | `FileReferenceChip`, `PreviewCodePane` |
| Activity page Outcomes | Shipped | Panel Outputs must stay same data source |

## Reference screenshot mapping (structure, not skin)

Use the attached comps as **interaction / hierarchy** references. Re-skin into Gravitre’s existing operator shell (neutral surfaces, restrained emerald accent already in product) — **do not** clone Cowork’s warm cream + terracotta serif look.

| Reference pattern | Gravitre mapping |
|-------------------|------------------|
| Cowork Progress checklist (done / current / remaining) | Panel **Progress** — named steps from `progressSteps` / `pendingTask.params.steps` |
| Cowork Working folder / Artifacts list | Panel **Outputs** — BusinessOutcomes for this `conversationId` + hosted file chips when present |
| Cowork Context (connectors / tools / files) | Panel **Context** — connector/action bits + `contextExplanation` (Module B) |
| Manus nested step pills with per-step detail | Inline plan-bar / expandable parent step with child action pills (icons + short label; optional thin progress for `Running:`) |
| Manus “Computer” / Claude Artifacts split pane | Only for **web-renderable** outputs: reuse Preview·Code; for connector writes keep BusinessOutcome evidence; for Office blobs keep file chips (no fake PDF live preview) |
| Chat vs Cowork dual mode diagram | Gravitre stays **one Chat surface**: simple turns = inline-only; multi-step (≥3) = additive panel — not a second top-level product tab |
| Landing composer + discovery chips (Manus / Cowork) | Polish `/ai` landing composer + example prompts; do **not** invent a fake “Plugins > Sales > commands” tree unless wired to real Marketplace packs / saved prompts |

## Hard constraints

- Visual redesign of Chat (`/ai`) only. No new sidebar destinations. No resurrecting retired peers.
- Panel appears only when step count ≥ 3; under-threshold stays inline-only.
- Panel is **additive** — never remove the inline BusinessOutcome card from the transcript.
- Outputs section = same `businessOutcomes` API filtered by `conversationId` (link to Activity). No new store.
- Preview fidelity honesty: evidence card for connector writes; file chip for hosted docs; Preview·Code only for HTML/SVG/md already produced.
- Preserve IA consolidation (Activity hub) and browser-extension approval flow.
- Avoid: purple-indigo gradient dashboards; warm cream + terracotta serif Cowork clone; broadsheet newspaper; glow stacks; emoji decoration; pill-cluster clutter; inventing file generation just to fill Outputs.

---

## Paste into v0

```text
Redesign Gravitre Chat (/ai) so multi-step work feels like Cowork/Manus agentic clarity — without cloning their skins or inventing new product modes.

PRODUCT
Gravitre is an enterprise operator: governed connector writes, BusinessOutcomes, and durable chat artifacts. Chat is one surface (not a separate “Cowork” tab). Simple asks stay compact; multi-step work (≥3 planned/executed steps) adds a persistent right panel. Functional wiring already exists — this is visual + interaction fidelity.

ATTACHED REFERENCES (structure only — re-skin to Gravitre operator UI)
1) Claude Cowork — right panel cards: Progress checklist, Working folder / outputs, Context (connectors/tools). Soft cards, generous radius, calm hierarchy.
2) Claude Chat vs Cowork diagram — conversational bubbles vs agentic checklist → finished deliverable. Gravitre = one Chat; panel is the agentic affordance, not a second app.
3) Manus step list — named parent step + nested pill rows with action icon + short label + optional mini progress for the active step.
4) Manus / Claude Artifacts split — left chat, right workspace for the current artifact with Preview | Code when the output is web-renderable.
5) Landing composers (Manus / Cowork-style) — centered greeting, large rounded composer, light discovery chips/examples. Adapt; do not copy cream/terracotta branding.

WHAT EXISTS TODAY (reuse; do not rebuild data)
- Threshold: auto-show panel when steps ≥ 3 (SIDE_PANEL_STEP_THRESHOLD).
- Progress data: SSE progressSteps as "Running: …" / "Completed: …" / "Step N/M: …" plus pendingTask.params.steps labels.
- Outputs data: GET business outcomes filtered by conversationId (same as Activity). Hosted files already render as FileReferenceChip; PreviewCodePane for HTML/SVG/md.
- Inline BusinessOutcomeView (density=chat) with real vendor/Gravitre evidence links — KEEP in transcript.
- Files: apps/web/components/gravitre/assistant/task-side-panel.tsx, research-plan-panel.tsx, file-reference-chip.tsx, preview-code-pane.tsx, business-outcome-view.tsx; apps/web/app/ai/_components/ai-workspace.tsx, ai-landing.tsx.

COMP 1 — Landing (no active multi-step task)
- Calm centered greeting + large composer (attachment affordance OK if it maps to existing upload/context).
- Example / mode chips already in product — refine layout; no fake “Plugins > Sales > slash-commands” tree unless tied to real Marketplace packs or saved prompts.
- No right panel on landing / single-step empty state.

COMP 2 — Active simple turn (under threshold)
- Transcript + inline plan-bar with NAMED steps (Manus-like pills OK).
- BusinessOutcome / file chip / Preview·Code appear inline when those outputs exist.
- Right panel ABSENT.

COMP 3 — Active multi-step task (panel ON, ≥3 steps)
Two-column workspace:
LEFT — chat transcript (scrolls). Keep inline BusinessOutcome cards and compact artifact chips. Parent step can expand to show child action pills (icon + label; spinner/progress only on current Running step).
RIGHT — persistent Task panel (~280–320px, sticky), three collapsible cards:
  A) Progress — vertical checklist: done (check), current (number/spinner), remaining (muted number). Named labels only (e.g. “Create contact list”, “Search contacts”) — never “Routing tier: research”. Optional “Step 2 of 5” counter in header.
  B) Outputs — task-scoped BusinessOutcomes (title + one-line summary → Activity). If hosted files exist, show file-reference chips here too. Empty state: “Outputs for this task appear here and on Activity.”
  C) Context — active connector/action lines + short contextExplanation. Optional “suggested connectors” only if driven by real disconnected-tool signals already in product — no fake Notion/Linear list.
Inline artifact card stays in chat; panel does not replace it.
When user opens a web-renderable artifact, allow a Preview | Code workspace treatment (reuse PreviewCodePane patterns). Do NOT fake live preview of PDF/DOCX.

COMP 4 — States
- Panel hidden (<3 steps)
- Panel visible, mid-run (mixed done/current/pending)
- Panel visible, complete (all checks + outputs populated)
- Empty Outputs / empty Context
- Light + dark if the app already supports both

VISUAL DIRECTION (Gravitre, not Cowork clone)
- Operator clarity: neutral surfaces, subtle borders, restrained accent consistent with current Chat/emerald product language.
- High radius cards OK; avoid warm cream + terracotta serif hero look from the Cowork screenshots.
- No purple-indigo gradient dashboards, broadsheet layouts, glow stacks, emoji chrome, or dense pill clusters.
- Typography: expressive heading allowed on landing only; UI labels stay product sans already in system.

HARD DO-NOT
- No new top-level nav or “Cowork” product tab.
- No new data stores; panel must use existing progressSteps / pendingTask / businessOutcomes / hosted files.
- No removing inline BusinessOutcome from the transcript.
- No inventing Office generation or speculative plugins just to fill the panel.
- No regression to Activity Outcomes page or browser-extension approval flow.

DELIVERABLES
1) Desktop comps: Landing, simple turn (panel off), multi-step (panel on) with Progress/Outputs/Context filled from realistic Gravitre labels (Apollo list create, search contacts, add to list).
2) One annotation frame mapping each panel section → data source.
3) Optional: collapsed panel / mobile stacked panel below transcript.
4) Component breakdown suitable for Next.js + existing shadcn/Tailwind tokens in apps/web — name components to extend TaskSidePanel / ResearchPlanPanel / AiLanding rather than greenfield shells.
```

## Implementation notes (for Cursor after v0)

- Prefer editing `task-side-panel.tsx`, `research-plan-panel.tsx`, `ai-landing.tsx`, and layout in `ai-workspace.tsx`.
- Keep `shouldShowTaskSidePanel` / threshold tests green.
- Re-run `scripts/verify-chat-progress-ux-v2-live.py` + `e2e/task-side-panel.spec.ts` after visual ship.
- Evidence bar: tip `/health` git_sha + live artifact before claiming done.

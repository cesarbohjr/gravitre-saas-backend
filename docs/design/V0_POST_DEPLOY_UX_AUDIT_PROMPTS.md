# Gravitre Post-Deploy UX Audit — v0 Frontend Prompts (G1–G5)

Paste these into [v0.dev](https://v0.dev) **after** backend commit `3aaea68` is deployed. **Do not implement in Cursor unless explicitly requested.**

Companion docs:
- [`docs/delivery/WORK_SECTION_FRONTEND_AUDIT.md`](../delivery/WORK_SECTION_FRONTEND_AUDIT.md) — WORK pages baseline (Jun 2026)
- [`docs/delivery/CONNECTOR_WORKFLOW_STEP_HANDLERS.md`](../delivery/CONNECTOR_WORKFLOW_STEP_HANDLERS.md) — vendor `invoke_tool` compile
- [`docs/delivery/STA-5_STREAMING_VERIFICATION.md`](../delivery/STA-5_STREAMING_VERIFICATION.md) — assistant SSE streaming
- [`docs/integration/V0_BACKEND_SYNC.md`](../integration/V0_BACKEND_SYNC.md) — API sync checklist

Stack: Next.js App Router, React 19, TypeScript, Tailwind v4, shadcn/ui, SWR, Framer Motion, `@ai-sdk/react` (`useChat`), existing `apps/web/lib/fetcher.ts` and `apps/web/components/gravitre/premium-effects.tsx`.

Visual baseline: match production — light/dark theme, Gravitre AppShell, trial banner, Admin/Lite toggles. **Discovery-first: read existing files completely before editing.**

---

## Master audit prompt (run first)

```
You are the frontend design lead auditing Gravitre Operator AI after a production
backend release. Your job: REVIEW existing wired UI, find gaps vs new backend
behavior, and add surgical UX improvements only — no layout rewrites, no new npm
dependencies unless lottie-react is justified.

BACKEND CHANGES TO REFLECT IN UI (already shipped in code — verify wiring):

1. CONNECTOR WORKFLOW STEPS
   Builder connector nodes (HubSpot, Jira, NetSuite, etc.) now compile to
   executable type "invoke_tool" with config.action = "{vendor}.{action}".
   Previously they silently became "noop". UI must show correct step type on
   save/preview/run and never label vendor actions as no-op.

2. ASSISTANT TRUE STREAMING (STA-5)
   POST /api/assistant/chat streams SSE events: text-start, text-delta, text-end
   (real provider tokens via ModelRouter.stream + failover). UI must render
   incremental tokens, not wait for full completion blob.

3. WORK SECTION PREMIUM UX (prior pass — verify, don't rebuild)
   Operator, Assistant, Search (/chat), Agents, Assignments: skeletons, error
   retry, empty states, ⌘K semantic search on WORK pages. Polish gaps only.

4. RUN OPS (verify)
   Execution timeline, step retry, pause/resume, approval gates — already wired;
   ensure invoke_tool steps show action name + connector in expanded detail.

PROCESS:
- Read target files completely before changing anything
- Match existing card/badge/button patterns
- Use SWR + existing API proxies under apps/web/app/api/*
- Mock only when API field missing; prefer live data
- Light + dark theme; respect prefers-reduced-motion
- List files you changed and manual test checklist at end

TARGET ROUTES (priority order):
1. /workflows/[id]/builder
2. /assistant
3. /runs/[id]
4. /connectors/[id] and /connectors
5. WORK pages: /operator, /chat, /agents, /assignments
```

---

## G1 — Workflow Builder: Vendor Connector Steps (`invoke_tool`)

**Backend:** `backend/app/workflows/builder_sync.py` — connector nodes → `invoke_tool`  
**Primary files:** `apps/web/app/workflows/[id]/builder/page.tsx`, `apps/web/components/workflows/meson-copilot-panel.tsx`, `apps/web/components/gravitre/workflow-card.tsx`

```
DO NOT redesign the canvas. Enhance connector node UX so operators trust that
vendor actions will actually run in production.

FIND AND READ:
- apps/web/app/workflows/[id]/builder/page.tsx (connector node rendering, save/sync)
- apps/web/lib/connector-actions.ts (or equivalent catalog fetch)
- components/workflows/meson-copilot-panel.tsx
- components/gravitre/workflow-card.tsx (connector dependency chips)

REQUIREMENTS:

1. COMPILED STEP PREVIEW (inspector / node detail panel)
   When a connector node has vendor + selectedAction, show:
   - Badge: "Runs as invoke_tool" (not "noop" / not generic "task")
   - Monospace action key: e.g. hubspot.contacts.search
   - Connector status pill: connected / disconnected / missing
   - If action catalog marks implemented:false → amber "Action not available" banner

2. PRE-SAVE VALIDATION
   Block or warn on Save/Publish when:
   - connector node has selectedAction but no connector_id bound
   - vendor disconnected in connector library
   - selected action not in catalog or not implemented
   Use toast + inline field error; primary button disabled until fixed.

3. WORKFLOW CARD / LIST METADATA
   On workflow cards, connector dependency row must include vendor invoke_tool
   actions (not only slack/email). Show count: "3 connectors · 5 actions".

4. MESON PANEL ALIGNMENT
   When last added node is type connector with vendor action, Meson suggestions
   should reference the action name and suggest logical next steps (agent step,
   slack notify, second connector read). Wire to existing POST /api/meson/suggestions.

5. DRY-RUN / PREVIEW COPY
   In run preview or digital twin UI, label steps:
   "HubSpot — Search contacts (invoke_tool)" instead of "noop" or "task".

EMPTY / ERROR:
- No connector selected: dashed border + "Select connector & action"
- Catalog loading: skeleton on action dropdown

Do not add new backend routes. Compile preview can derive from client-side node
state mirroring backend graph_to_definition rules.
```

---

## G2 — Assistant: Real-Time Token Streaming (STA-5)

**Backend:** `ModelRouter.prepare_stream` + `stream`; SSE `text-delta` events  
**Primary files:** `apps/web/app/assistant/page.tsx`, `apps/web/app/api/chat/route.ts` (proxy)

```
READ apps/web/app/assistant/page.tsx and the /api/chat proxy completely.

The backend now streams true provider tokens (text-start / text-delta / text-end).
Audit the useChat + DefaultChatTransport wiring and fix any UX that still feels
"batch pasted" after response completes.

REQUIREMENTS:

1. STREAMING FEEDBACK
   - While status === "streaming": show TypingIndicator OR blinking caret at end
     of assistant message (use existing premium-effects TypingIndicator if present)
   - Message text grows incrementally per delta — no full-block swap mid-stream
   - Submit/stop: Stop button visible during stream; disabled send until finish

2. STREAM HEALTH
   - If stream ends with empty assistant content → inline error card + retry
   - Parse proxy errors (503 guardrails, 429 rate limit) with actionable copy
   - Preserve conversation_id on retry so thread is not orphaned

3. MODE / MODEL SELECTOR (verify prior work)
   - Fast / Standard / Deep / Agent modes still pass mode in body
   - Model override persists; placeholder changes per mode
   - Do not regress sidebar skeleton, history error retry, org context pill

4. TOOL ACTIVITY DURING STREAM
   - If tool-call events appear in stream, show compact tool row above tokens
   - Completed tools: checkmark; running: spinner (match F4 spec)

5. ACCESSIBILITY
   - aria-live="polite" on streaming message region
   - prefers-reduced-motion: disable caret blink, keep instant chunk updates OK

API: POST /api/assistant/chat (stream) via existing /api/chat proxy.
Do not change backend. Test with a short prompt ("Say hello in one sentence").
```

---

## G3 — Run Detail: `invoke_tool` Step Transparency

**Primary files:** `apps/web/components/runs/execution-timeline.tsx`, `apps/web/app/runs/[id]/page.tsx`

```
Enhance run monitoring so connector tool steps are legible to CS and operators.

READ execution-timeline.tsx and runs/[id]/page.tsx completely.

REQUIREMENTS:

1. STEP HEADER
   For stepType === "invoke_tool" (or output.action present):
   - Title: human name from step definition
   - Subtitle: "{vendor}.{action}" parsed from output.action or config
   - Icon: ConnectorIcon for vendor prefix when recognizable

2. EXPANDED DETAIL
   Show structured sections:
   - Input params (redact secrets)
   - Result: success/fail badge, error_code, connector_id
   - Duration + retry count if present
   - Link: "View connector" → /connectors/[id] when connector_id known

3. FAILED INVOKE_TOOL
   - Red border + concise error_message
   - [Retry step] uses existing POST /api/runs/{id}/steps/{stepId}/retry
   - Suggest fix when error_code indicates auth (reconnect connector CTA)

4. PARALLEL / APPROVAL (verify no regression)
   - Paused runs: amber banner + Resume
   - Approval gates unchanged

Poll GET /api/runs/{id} every 2s while running or paused (existing behavior).
```

---

## G4 — Connectors Hub: Workflow Linkage & Action Readiness

**Primary files:** `apps/web/app/connectors/page.tsx`, `apps/web/app/connectors/[id]/page.tsx`, connector catalog components

```
Connectors are now first-class workflow citizens via invoke_tool steps. Update
connector surfaces to reflect usage and readiness.

READ connector list + detail pages completely.

REQUIREMENTS:

1. CONNECTOR DETAIL — "Used in workflows"
   Section listing up to 5 workflows that reference this connector type via
   invoke_tool action prefix OR dedicated step types (slack_post_message, etc.).
   Data: GET workflow defs client-side filter OR backend context if available.
   Empty: "Not used in any workflow yet" + CTA "Add to workflow" → builder.

2. ACTION CATALOG UX
   For each action in v1/v2/v3 tiers:
   - Green "Ready" if implemented:true from GET /api/connectors/catalog
   - Gray "Planned" if implemented:false
   - "Add to workflow" secondary button on Ready actions → builder deep link
     with vendor + action pre-selected (query params: ?vendor=&action=)

3. CONNECT HEALTH + WORKFLOW WARN
   If connector disconnected but referenced in active workflow version:
   - Amber banner on detail page
   - Surface in CS dashboard integration health if already consumed

4. DEMO WORKFLOWS (catalog)
   If demo_workflows returned for vendor, show "Install demo" card with risk
   level badge (low/medium/high) and requires_approval flag.

Do not implement new OAuth flows. Link to existing connect CTAs.
```

---

## G5 — WORK Section Regression & Motion Polish

**Baseline:** [`WORK_SECTION_FRONTEND_AUDIT.md`](../delivery/WORK_SECTION_FRONTEND_AUDIT.md) — all items marked Complete

```
Lightweight audit pass on WORK pages — fix regressions and add motion polish only.

PAGES: /operator, /assistant, /chat, /agents, /assignments

READ each page file completely. Use WORK_SECTION_FRONTEND_AUDIT checklist.

VERIFY (fix if broken):
- WorkSectionErrorCard + retry on all five pages
- Skeleton loaders visible on slow network (remove fallbackData that hides loading)
- ⌘K focuses semantic search on WORK pages; Command Palette elsewhere
- Assignments ?approval=1 deep link opens approval modal
- Agents: success rate colors, ACTIVE glow, AgentModelBadge tooltips
- Search: type-ahead debounce 300ms, rotating placeholders, grouped results

ADD (motion — match F5 global system in V0_AI_INTELLIGENCE_PROMPTS.md):
- Staggered list entrance on Agents grid and Assignments rows
- Hover scale 1.01 on interactive cards (already on Agents — extend consistently)
- Success toast with brief PulseRing on assignment approve
- prefers-reduced-motion respected everywhere

Do not rebuild layouts. No new API routes.
```

---

## Backend → UI dependency matrix

| Prompt | Backend capability | Key API / behavior | UI gap to close |
|--------|-------------------|-------------------|-----------------|
| G1 | Builder `invoke_tool` compile | Save graph → `workflow_defs.definition.steps` | Stop showing vendor steps as noop; validate before publish |
| G2 | STA-5 token streaming | SSE `text-delta` on `/api/assistant/chat` | Incremental render + stream stop/error UX |
| G3 | InvokeToolHandler execute | Run step output includes `action`, success, error_code | Timeline labels + retry/connect CTAs |
| G4 | Action catalog + context packs | `GET /api/connectors/catalog`, workflow defs | Related workflows, implemented badges, deep links |
| G5 | WORK audit baseline | Existing WORK APIs | Regression + motion polish only |

---

## v0 deliverable checklist (paste at end of each prompt)

```
Before finishing, confirm:
[ ] Read all listed files — no duplicate components created
[ ] Light + dark theme checked
[ ] Loading, empty, and error states present
[ ] No new npm deps (unless lottie-react with justification)
[ ] TypeScript types updated for new props/state
[ ] Manual test steps written in PR description

Manual tests:
1. Workflow builder: add HubSpot connector node + action → save → verify step
   type invoke_tool in network response or preview UI
2. Assistant: send message → tokens appear incrementally → stop mid-stream works
3. Run detail: execute workflow with invoke_tool → expand step → see action key
4. Connector detail: shows related workflows or empty CTA
5. WORK pages: skeleton + error retry still work; ⌘K on /agents focuses search
```

---

## Suggested v0 session order

1. **Master audit prompt** — orient model, list files  
2. **G1** — highest impact (connector steps were silently noop)  
3. **G2** — assistant streaming feel  
4. **G3** — run transparency  
5. **G4** — connectors hub linkage  
6. **G5** — WORK regression sweep  

After v0 exports land in the repo, sync via [`V0_BACKEND_SYNC.md`](../integration/V0_BACKEND_SYNC.md) and run:

```bash
cd apps/web && npm run typecheck && npm run build
npm run smoke:ai-production:report
```

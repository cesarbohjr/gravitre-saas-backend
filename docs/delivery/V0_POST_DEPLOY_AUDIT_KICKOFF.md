# v0 Post-Deploy UX Audit — Kickoff (2026-06-16)

Production deploy verified for backend BUILD/INSIGHTS fixes. This doc captures the **production spot-check** and **ready-to-paste v0 prompts** for session 1 (G1 Builder + G2 Assistant).

**Open in v0:** https://v0.dev  
**Source prompts:** [`docs/design/V0_POST_DEPLOY_UX_AUDIT_PROMPTS.md`](../design/V0_POST_DEPLOY_UX_AUDIT_PROMPTS.md)

---

## Production spot-check (#1)

### App routes (unauthenticated)

| Route | Result |
|-------|--------|
| `/audit` | 307 → `/login` |
| `/workflows` | 307 → `/login` |
| `/metrics` | 307 → `/login` |
| `/runs` | 307 → `/login` |
| `/assistant` | 307 → `/login` |
| `/workflows/*/builder` | 307 → `/login` |

Auth gate works as expected. Logged-in UI must be verified manually in browser or via API (below).

### Backend API (authenticated smoke org)

Run:

```bash
python scripts/smoke-build-insights-spotcheck.py --json docs/delivery/build-insights-spotcheck-latest.json
```

Latest report: [`build-insights-spotcheck-latest.json`](./build-insights-spotcheck-latest.json) (2026-06-16)

| Check | Result | Detail |
|-------|--------|--------|
| `GET /api/audit` | **FAIL 500** | Entitlement passes; Supabase query error (likely `audit_logs` schema/column mismatch in prod) |
| `GET /api/workflows/stats` | **PASS** | `overallSuccessRate: 100`, `totalRunsThisWeek: 83` |
| `GET /api/metrics/overview` | **PASS** | `totalRuns: 93`, `successRate: 100` |
| `GET /api/metrics/insights` | **PASS** | 1 insight, API-generated |
| `GET /api/metrics/weekly-throughput` | **PASS** | 7 days, target 3 |
| `GET /api/runs` | **FAIL 500** | Internal Server Error — investigate before v0 G3 run-detail work |

**Summary:** 4/6 API checks pass. Workflows footer + metrics dashboard data paths are healthy. Audit and runs need a backend fix (500, not 403/fake data).

### Frontend code audit (static)

| Page | Fake data removed? | Remaining gap |
|------|-------------------|---------------|
| `/workflows` | Yes — footer from `/api/workflows/stats` | None for P0 footer |
| `/runs` | Yes — no `fallbackRuns` | Poll every 10s |
| `/audit` | Yes — empty `fallbackData` only | Clear upgrade vs fetch errors |
| `/metrics` | Partial | MetricCard still shows `1,247`, `98.7%`, `1.8M`, `142ms` when API null; sparkline trends hardcoded |

**Manual browser pass (5 min after login):** confirm workflows footer, metrics chart, runs list, audit table match API — not demo numbers.

---

## v0 session 1 — paste order

1. **Master audit prompt** (orient) — from [`V0_POST_DEPLOY_UX_AUDIT_PROMPTS.md`](../design/V0_POST_DEPLOY_UX_AUDIT_PROMPTS.md) § Master  
2. **G1 — Builder `invoke_tool`** (below)  
3. **G2 — Assistant streaming STA-5** (below)

After G1/G2 exports land, sync via [`V0_BACKEND_SYNC.md`](../integration/V0_BACKEND_SYNC.md).

---

## G1 — Workflow Builder: Vendor Connector Steps (`invoke_tool`)

**Paste into v0:**

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

**Spot-check context for v0:** Backend `builder_sync.py` already compiles connector nodes to `invoke_tool`. Production API smoke passes; UI may still label steps as noop in preview/inspector.

---

## G2 — Assistant: Real-Time Token Streaming (STA-5)

**Paste into v0 after G1 export:**

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

**Spot-check context for v0:** Production smoke `assistant_chat` step passes (SSE deltas). Recent merge on `assistant/page.tsx` (commit `5f00379`) may have streaming changes — read file before editing.

---

## Next v0 sessions (after G1 + G2)

| Order | Prompt | Focus |
|-------|--------|-------|
| 3 | G3 | Run detail `invoke_tool` step transparency |
| 4 | G4 | Connectors hub workflow linkage |
| 5 | G5 | WORK section regression + motion |

---

## After v0 exports

```bash
cd apps/web && pnpm run build
npm run smoke:ai-production:report
python scripts/smoke-build-insights-spotcheck.py --json docs/delivery/build-insights-spotcheck-latest.json
```

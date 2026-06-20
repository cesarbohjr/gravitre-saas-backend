# Marketing copy — Strict policy review (Decision 3)

**Status:** Draft applied in repo; **pending product/marketing approval** before treating as final.

**Policy:** No maturity-ladder numbers. No guaranteed multi-agent real-time execution. Connector actions framed as conditional on connected integrations and per-run verification.

---

## Files changed

| File | What changed |
|------|----------------|
| `apps/web/app/(marketing)/changelog/page.tsx` | v2.4.0 + v2.0.0 release copy |
| `apps/web/app/(marketing)/blog/page.tsx` | Featured post title + excerpt |
| `apps/web/app/(marketing)/page.tsx` | Homepage “Monitor & act” step |
| `apps/web/app/(marketing)/features/page.tsx` | Assistant + connectors bullets |
| `apps/web/app/(marketing)/docs/[...slug]/page.tsx` | AI Operator + Introduction sections |

---

## Replacement copy by file

### `changelog/page.tsx` — v2.4.0

- **Description:** Coordinate multiple agents on complex tasks with defined roles. Each sub-agent completes its scoped work; results are aggregated after completion—not live shared memory.
- **Highlights:** Parallel sub-agent jobs via the agent queue · Council-style aggregation of completed subtask results · Collaboration graph in workflow builder · Parallel job scheduling improvements

### `changelog/page.tsx` — v2.0.0

- **Description:** Major release with durable async operator analysis, ReAct-style reasoning when integrations are connected, and structured task outputs.
- **Highlights:** Async operator analysis jobs · ReAct-style reasoning on connected integrations · Structured plans, findings, and recommended actions · Conversation memory improvements · Enhanced error handling · Redesigned dashboard

### `blog/page.tsx` — featured post

- **Title:** Introducing AI Operator 2.0: Smarter Operator Analysis
- **Excerpt:** AI Operator 2.0 brings durable async analysis, ReAct-style reasoning when integrations are connected, and clearer structured outputs. Connector actions depend on your setup and are verified per run.

### `page.tsx` — homepage step 3

- **Description:** Agents answer questions and, when integrations are connected, can gather data and take actions through your linked systems. Each run shows what was analyzed and what was executed.

### `features/page.tsx` (additional strict pass — STA-262)

- **Value prop:** Accelerated execution — no 10x claim; conditional on connected integrations
- **Integrations heading:** 100+ integrations when configured
- **Connector bullets:** Sync when connected (not Real-time sync)
- **Meson bullet:** Ships configured workflows for review before production
- **Capabilities grid:** Timely insights / link tools when integrations are connected

### `features/page.tsx` (prior pass)

- **Assistant bullets:** Conversational AI interface · Context-aware responses · Multi-agent workflows (when configured) · Async task analysis with progress tracking
- **Connectors body:** When integrations are connected, agents can read, write, and take actions across your linked tools. Each run reflects what was executed—not every action is guaranteed without a connected integration.

### `docs/[...slug]/page.tsx`

- **AI Operator description:** Learn how to use natural language to plan and automate tasks. The AI Operator understands your intent and prepares execution plans; connected integrations enable actions when configured.
- **What is the AI Operator?:** …prepares an analysis and action plan. Execution through connected integrations depends on your setup; sensitive steps may require your approval before they run.
- **Introduction — What is Gravitre?:** …Connector actions run when integrations are linked and configured; the product shows what each run analyzed and executed.

---

## Approver checklist

- [ ] Product/marketing confirms no overclaim vs current product behavior
- [ ] Sales deck + demo script audited separately (not in this PR)
- [ ] Re-enable stronger claims only after `execution_mode` is user-visible and Swarm trust fix ships

**Route to:** product/marketing owner for sign-off on this diff.

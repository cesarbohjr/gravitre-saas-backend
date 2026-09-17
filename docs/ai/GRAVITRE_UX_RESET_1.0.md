# GRAVITRE UX RESET 1.0 — first deliverable (audit only)

**Status:** A–Z complete as a **code inspection**. Not a production PASS. **No `apps/web` production UI was changed.**

**Stop:** Cesar approval required before implementation.

**Interactive board:** Cursor canvas `gravitre-ux-reset-1.canvas.tsx` (workspace canvases folder).

**Rule:** `.cursor/rules/gravitre-ux.mdc` (globs `apps/web/**/*.{tsx,ts,css}`).

Evidence class: repository read of `apps/web` on 2026-09-17. Dual AI paths `/ai` and `/agents/[id]/chat` remain until they share one runtime.

---

## A. Product-wide UX audit

Gravitre already has Nodus tokens, Nucleo icons, Motion, and a floating AI workspace. The failure mode is **component substitution for information architecture**.

Recurring pattern: represent a simple job with cards inside cards, tabs, pills, equally weighted buttons, and nested panels. That produces an AI-generated SaaS dashboard rather than ASK → UNDERSTAND → ACT → SHOW RESULT.

Highest-cost areas:

| Area | What the user is doing | What the UI does instead |
| --- | --- | --- |
| AI | Ask Gravitre | Three live `useChat` instances + presentation names that do not match the spec |
| Connectors | Connect a service | Large logo/card catalog |
| Settings | Change a preference | Card per group |
| Training / model studio | Configure training | Pills + tabs + cards |
| Intelligence admin | Inspect learning | Nested containers around the graph |
| Agent surfaces | Find / talk to an agent | Avatar cards + a second chat product at `/agents/[id]/chat` |

What already works and must not be undone:

- `GravitreAIAuthGate` unmounts AI when logged out and purges stored conversation on logout.
- `/assistant` redirects to canonical `/ai`.
- Marketing providers stay off authenticated AI chrome.
- Meson toolbar is **not** a chat runtime.
- Window controls were partially unified in `apps/web/lib/chat-window-state.ts`.

---

## B. Page-purpose map

| Route | Primary job | Primary object | Primary action | Hide until needed |
| --- | --- | --- | --- | --- |
| `/home` | See what needs attention | Work queue | Open next item or Ask | Extra widgets |
| `/ai` | Talk to Gravitre | Conversation | Ask | History, sources, traces |
| `/agents` | Find a teammate | List / graph | Open or assign | Avatar galleries |
| `/agents/[id]` | Configure one agent | Agent | Edit / run | Memory, capabilities as inspector |
| `/agents/[id]/chat` | Ask in agent scope | Same conversation | Ask (scoped) | A second product |
| `/workflows` | Find and run work | Workflow list | Open / run | Status furniture |
| `/connectors` | Connect a service | Catalog | Connect | Giant cards |
| `/intelligence` | Understand relationships | Graph + selection | Inspect / Ask | Card stack around graph |
| `/intelligence/performance` | Diagnose runs | Metrics → pipeline → trace | Select a failing run | Disconnected KPI cards |
| `/settings` | Change a preference | Setting row | Save | One card per field |
| `/marketplace` | Install capability | Asset list | Install | Decorative tiles |
| `/activity` | Review what happened | Event list | Open a run | Dashboard wrapping |

**Complexity budget (target):** one primary region, one primary action, one in-page nav layer, no nested cards, no inspector until selection.

---

## C. Component-debt inventory

| Component | Routes | Purpose | Duplication | Disposition |
| --- | --- | --- | --- | --- |
| `AiWorkspace` + `useChat` | `/ai`, float, expanded, fullscreen, mobile sheet | Canonical conversation | Shells exist; runtime is the right owner | **Keep** as the runtime |
| `GravitreAIWorkspaceProvider` | Root layout | Presentation + snapshots | Snapshots are not the live chat | **Refactor** so presentation names match spec; hoist live chat here or keep one owner below it |
| `agents/[id]/chat` `useChat` | Agent chat | Agent-scoped ask | Full second runtime | **Consolidate** |
| `AskGravitreComposer` `useChat` | Intelligence | Mini chat | Third runtime; comments admit isolation | **Remove** as runtime; **Keep** as entry that summons workspace |
| `AskGravitreEntry` | Intelligence overview | Link into `/ai` | Navigates away | **Refactor** to summon workspace with context |
| `/assistant` | Legacy | Deep link | Redirect only | **Preserve** |
| `GravitreAIAuthGate` | App providers | Hide AI when logged out | Single gate | **Preserve** |
| Meson popup | Workflows / insights | Non-chat insights | Not chat | **Preserve** (do not fold into chat) |
| Marketing demo chat | Marketing | Fake conversation | Isolated | **Preserve** isolation |
| `dev/ai-workspace-preview` | Internal | Prototype | Not product | Fold into this program; do not ship as a second UX |
| Task / sources / execution panels | AI shells | Expert detail | Often permanent | **Refactor** to contextual inspector |
| Settings card wrappers | `/settings*` | Grouping | Card-first | **Refactor** to rows |
| Connector tiles | `/connectors` | Discovery | Card grid | **Refactor** to compact row/tile + real logos |

---

## D. Card-overuse inventory

Justified: dashboard widgets (modular monitoring); connector **discovery** may use a compact tile; marketplace list density.

Not justified: card around every setting; card around the relationship graph; card around every metric on Performance; card around every assistant message; empty-state suggestion **card grids**; nested metric cards inside dashboard widgets.

---

## E. Tab-overuse inventory

Justified later: parallel views of **one selected object** (run overview vs trace).

Not justified as the first IA move: agent profile tab strips; workflow builder mode-as-tabs; settings clusters; training/model studio; AI mode tabs on empty chat (`auto` / `execute` / `chat` / `find` as chrome).

---

## F. Pill / badge overuse

Justified: run status; active filter chip; removable selection.

Not justified: mode selectors, metadata, category rows, nav, “modern” action chips on training and workflow builder.

---

## G. Button / action hierarchy

Many screens show 3–6 visually equivalent buttons (Connect, Ask, Filter, New, Export).

Rule: **one** obvious primary. Everything else is text, icon, overflow, or appears after selection.

AI nav should **focus or open** the canonical workspace, not necessarily route the user off their work. `/ai` remains a valid fullscreen deep link.

---

## H. AI chat duplication topology (priority zero)

```
CURRENT

GravitreAIWorkspaceProvider (presentationMode, pageContext, snapshots)
        │
        ├── AiWorkspace.useChat          ← live thread for /ai + float + expanded + fullscreen
        ├── agents/[id]/chat.useChat     ← second live thread (agent-scoped API config)
        ├── AskGravitreComposer.useChat  ← third live thread (Intelligence)
        ├── Marketing fake chat          ← not authenticated product
        └── Meson toolbar                ← not chat

Presentation names today: helper | float | expanded | fullscreen
+ floatWorkspaceOpen
+ /ai “embedded” surface (page IS the chat; launcher hidden)

COMPACT is not a named mode. Float is resizable and covers that class.
```

Restore already intends: launcher click restores previous mode (`restoreTargetMode` in `chat-window-state.ts`). Do not create a new session on launcher click.

---

## I. AI runtime / state topology

| Concern | Current | Risk |
| --- | --- | --- |
| Conversation store | No Zustand; React context snapshots + per-route `useChat` | Snapshots can drift from the live instance |
| Session / persistence | localStorage thread id + sessionStorage messages; purged on logout | Good; must not purge on presentation change |
| Voice | Inside AiWorkspace | A remount of a second `useChat` can restart STT/TTS |
| Tools / execution | Chat execution panel on the live workspace | Must not cancel on resize unless architecture requires it |
| Auth | AuthGate children unmount when `!user` | Correct |
| Context | `pageContext` captured; Ask composer does not drive the live workspace | Duplicate context assembly if Intelligence chat stays |

---

## J. Proposed canonical AI architecture

```
                    ┌────────────────────────┐
                    │ Gravitre AI Runtime    │
                    │ Conversation / Context │
                    │ Tools / Voice / State  │
                    └────────────┬───────────┘
                                 │
                    ┌────────────▼───────────┐
                    │ Gravitre AI Workspace  │
                    └────────────┬───────────┘
                                 │
             ┌───────────────────┼────────────────────┐
             │                   │                    │
        MINIMIZED             COMPACT          EXPANDED/FULLSCREEN
```

Mapping from shipped names (do not big-bang rename without tests):

| Spec | Today |
| --- | --- |
| MINIMIZED | `helper` + `floatWorkspaceOpen === false` |
| COMPACT | `float` (name it; default size 500–600px class) |
| EXPANDED | `expanded` |
| FULLSCREEN | `fullscreen` **and** `/ai` embedded |

`/ai` and `/assistant` render fullscreen of the **same** instance. `/agents/[id]/chat` is a **scoped context** on that instance, not a second `useChat`. Ask Gravitre opens the workspace with route + selection.

Deep links (`c`, `m`, `prompt`, `mode` query params) stay compatible.

---

## K. ChatGPT interaction-pattern findings

Extracted principles only (not a visual clone):

- Composer is the hero; empty state is identity + ask, not a feature dashboard.
- History is a collapsible rail, not a second product.
- Chat vs longer work is a mode of one product.
- Tools and sources appear in the turn, then recede.
- Voice is a composer/conversation state.

---

## L. Perplexity interaction-pattern findings

- Ask → read → cite is the loop.
- Sources are first-class **after** the answer.
- A permanent ~30% sources column is the anti-pattern for Gravitre compact/expanded defaults.

---

## M. Manus interaction-pattern findings

- Conversation is the controller; artifacts are the work surface.
- Agent activity is shown when the system is working, with expand for detail.
- Confirm / takeover stays contextual — not a multi-agent console on every question.

---

## N. Gravitre-specific synthesis

Gravitre is an **operator** product: connectors, approvals, runs, graph, governance. That power should appear through **progressive disclosure** and **Ask**, not through more chrome.

Nodus: type, space, alignment, editorial rhythm. Not rounded white cards as the default object.

Mobile: launcher → sheet → fullscreen. No desktop drag-resize.

---

## O–R. Wireframes / prototypes

See canvas tabs **Wireframes**. Structure:

1. **Empty:** identity, one line, large composer, 2–4 text suggestions.
2. **Active:** message / response / disclosure links (Sources, Execution).
3. **Compact:** header + thread + composer; no history rail.
4. **Expanded:** thread remains central; rail/inspector only if useful.
5. **Fullscreen:** same workspace; `/ai` is this state.
6. **Minimized:** one launcher; restore thread.
7. **Sources:** expand after the answer.
8. **Agent execution:** inline one-liner → expand.
9. **Artifact:** conversation controls; document beside/over the thread.
10. **Mobile:** sheet, not a floating window.
11–14. **Agents / Relationships / Performance / Settings:** list+graph, graph-first, metrics-then-trace, rows not cards.

Each prototype’s interaction win is: **fewer decisions before the primary action**, not “looks cleaner.”

---

## S. Progressive-disclosure model

| Default | Reveal |
| --- | --- |
| Answer | Sources |
| One-line tool/agent status | Execution detail |
| Conversation | Artifact |
| No inspector | Selection |
| No history rail (compact) | Expanded/fullscreen, collapsible |
| Simple metric / graph | Inspect |

Novice and expert are **one product**.

---

## T. Contextual-AI model

Entry points labeled Ask Gravitre (Intelligence, and later Agents, Workflows, Connectors, Performance, Approvals, Runs) call `setPresentationMode` / open compact or expanded on the **existing** runtime and attach `pageContext` + selected entity.

The user should not copy/paste “I am on Learning → Relationships looking at X.”

Do not invent a second context assembler. Extend `GravitreAIPageContext` and existing selection state.

---

## U–X. Consolidate / remove / refactor / preserve

**U. Consolidate:** AiWorkspace shells, `/ai`, `/assistant`, agent chat route, Ask Gravitre entries, window controls.

**V. Remove as products:** `AskGravitreComposer` live `useChat`; compact-mode history/inspector furniture; empty-state card dashboards; duplicate helper icons.

**W. Refactor:** presentation vocabulary; agent chat as scope; Intelligence/Connectors/Settings/Performance IA; message chrome (no giant bordered cards).

**X. Preserve:** AuthGate; restore-on-launcher; `/ai` query params; Nucleo; Nodus tokens; Meson-as-not-chat; marketing isolation; conversation persistence across route change **when using the root-mounted workspace**.

---

## Y. Updated UX design rules

Shipped as `.cursor/rules/gravitre-ux.mdc`. Cursor must apply the checklist before new UI in `apps/web`.

---

## Z. Implementation plan (blocked on approval)

0. **Approval** — no production UI until Cesar signs this document (amend/reject allowed).
1. Presentation state machine: map helper/float to minimized/compact; keep restore tests green.
2. One `useChat` (or equivalent) owner; delete Ask composer runtime; agent chat becomes scoped presentation.
3. Preserve conversation, voice, in-flight tools across size and route changes (explicit tests).
4. Flatten empty state, composer, messages, sources, artifacts.
5. Contextual Ask Gravitre on remaining product surfaces.
6. Same IA pass: Agents, Relationships, Performance, Settings, Connectors.
7. Only then: Motion between presentation states (same physical workspace).

Suggested first slice after approval: **(1) + kill AskGravitreComposer runtime**, with `/ai` remaining fullscreen of the same workspace.

---

## Final design test (for later implementation)

If we can remove 30% of a screen without reducing capability, remove it, then ask again.

**Minimum interface for maximum capability.**

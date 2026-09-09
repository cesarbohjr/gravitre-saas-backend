# Gravitre AI Agent Workspace — Floating/Expandable Redesign

## First Deliverable: Architecture Audit & Proposal (STOP-BEFORE-PRODUCTION gate)

**Status: read-only audit + proposal. Zero production files changed by this document. Nothing here has been wired into `/ai`, `/agents/[id]/chat`, or any other live route.**

Per the governing prompt's own instruction (§53), this document delivers items 1–15 and 21–25 in full, and frames items 16–20 (the four high-fidelity prototypes + transition demo) as a concrete, scoped **Phase 0** to be built in an isolated, non-production route — not as fabricated screenshots. Building and screenshotting real interactive prototypes at 6 breakpoints is itself a multi-day implementation effort; claiming that work is "done" here without actually building it would violate this program's own evidence-linked-completion standard. Section C3 (Prototype Plan) below is the honest substitute: exactly what will be built, where, and how it will be reviewed, pending your go-ahead.

Every claim below is sourced from two read-only codebase audits ([Chat architecture audit](18e19f14-3ac7-4377-a1d3-8c983eadc682), [Shared UI infrastructure audit](2fc66b85-e8ec-49f8-ab44-d27a485a237f)) plus direct verification of the highest-stakes claims. File:line citations are given wherever a citable fact is stated; anything that is a recommendation/decision rather than a fact is labeled as such.

**⚠️ Addendum (added after initial drafting, before this doc was committed):** a *different, concurrent* session already shipped a small, unrelated "floating AI helper" directly to `main` (commit `8523bc1f`, "combo stack finish, dashboard presets, floating AI helper"). See Part D below — it does **not** implement this spec and creates a real naming/UX collision that needs a decision.

---

## PART A — CURRENT STATE (spec §42–43)

### A1. Existing routes (spec §42 "CURRENT ROUTE")

| Route | Role | Evidence |
|---|---|---|
| **`/ai`** | Canonical unified AI chat (Answer/Search/Execute inline). This is the real target for "the AI chat." | `apps/web/app/ai/page.tsx:38-47`, `apps/web/lib/app-routes.ts:7-9` |
| **`/agents/[id]/chat`** | Per-agent chat variant — same transcript/composer stack, but a **separately implemented, separately persisted** thread | `apps/web/app/agents/[id]/chat/page.tsx:97-101` |
| `/assistant`, `/operator` | Legacy — redirect to `/ai` / `/ai?mode=chat`, not separate UIs | `apps/web/app/assistant/page.tsx:4-6`, `apps/web/app/operator/page.tsx:4-6` |
| `/chat`, `/search` | **Not chat.** Universal Search over org records — returns links, not conversational replies. Commonly confused with the AI chat by name only. | `apps/web/app/chat/page.tsx:707-720` |

**There was no existing floating/global chat overlay anywhere in the app when this audit began.** Chat was two separate full-page experiences. (See Part D — this changed mid-audit, but not in a way that fulfills this spec.)

### A2. Existing component tree (spec §42)

**`/ai`** (`apps/web/app/ai/_components/ai-workspace.tsx`, **2,558 lines**):
```
AiWorkspace
├── ConversationSidebar        (left — thread history)
├── Center column
│   ├── Header: ChatSessionControls, AiVoiceAgentPicker, ChatThemePicker, activity toggle
│   ├── AiLanding (empty state) / ResearchScopePrompt / ResearchPlanPanel / ResearchCascadePanel
│   ├── ChatTranscript          (message list, streaming, tool chips, approvals)
│   ├── TaskSidePanel           (inline sub-panel, lg+ only, NOT a 4th shell column)
│   └── SharedChatComposerControls (input, voice, file picker)
├── LiveActivityRail            (right — toggled)
└── ConnectedFilePickerDialog
```

**`/agents/[id]/chat`** (`apps/web/app/agents/[id]/chat/page.tsx`, **~690 lines**):
```
AgentChatPage
├── Header: PersonaSelector, ChatThemePicker, Knowledge link
├── ChatTranscript              (same component, no approval props wired)
└── SharedChatComposerControls  (same component, no file picker)
```

**Both pages independently instantiate their own `useChat`, voice hooks, and persistence logic.** `ChatTranscript` and `SharedChatComposerControls` are the only genuinely shared leaf components; everything above them is duplicated, not shared.

### A3. Existing layout (spec §42 "CURRENT LAYOUT / LEFT / CENTER / RIGHT PANEL")

`/ai` is effectively 3-panel on desktop:

| Panel | Component | Content today |
|---|---|---|
| **Left** | `ConversationSidebar` | Thread list (grouped by recency), search, date filters, pin/rename/archive/delete, new-conversation |
| **Center** | `ChatTranscript` + `SharedChatComposerControls` | Streaming, tool calls, approvals (HITL, inline in last assistant bubble), execution results (`ChatExecutionPanel`), artifacts, business outcomes, research cascade/scope, voice |
| **Right** | `LiveActivityRail` (toggle) + inline `TaskSidePanel` | Meson/advisor context, running/recent workflow runs, connector health, progress steps |

`/agents/[id]/chat` is **single-column only** — no left history, no right rail, and critically: **no approvals, no execution panel, no file picker wired at all** (`apps/web/app/agents/[id]/chat/page.tsx:591-603` passes no approval props to `ChatTranscript`). This is a real, pre-existing functionality gap between the two surfaces, not something introduced by this redesign — flagged for a decision in Part B.

Both pages render full-page inside a page-owned `<AppShell>`; chat is not portal-rendered and does not currently reflow anything (it *is* the page content, under the global nav shell).

### A4. Existing state ownership (spec §42 "CURRENT STATE MANAGEMENT")

No Zustand/Redux/Jotai anywhere in chat. Pattern is React `useState` + SWR + `@ai-sdk/react`'s `useChat` + `localStorage`/`sessionStorage`:

| Concern | Mechanism | Evidence |
|---|---|---|
| Streaming messages | `useChat` + `DefaultChatTransport` → `/api/chat` | `ai-workspace.tsx:451-534` |
| Thread list | SWR + `conversationsApi` | `ai-workspace.tsx:374-395` |
| Active conversation id | `useState` + localStorage | `ai-workspace.tsx:256-259`, `ai-conversation-storage.ts:3-40` |
| Message cache | sessionStorage | `ai-conversation-storage.ts:42-67` |
| Tool state | Derived from `UIMessage.parts` on every render — **no store** | `chat-transcript.tsx:59-82` |
| Voice duplex | `useVoiceDuplexSession` hook, local to the page | `ai-workspace.tsx:1681-1768` |
| Approvals | `pendingTask` / `dialogueMode` / `executionGate` local state | `ai-workspace.tsx:293-321` |
| Page/route context | **Not captured at all** — no `usePathname()`-driven context injected into `/api/chat` | confirmed absent in both pages |

**Two dead-but-defined pieces of state, worth knowing before "preserving all existing functionality":**
- `activeBusinessSignals` is fetched and set (`ai-workspace.tsx:297,516-580`) but **never rendered anywhere** — no banner component consumes it today. It is not visible functionality to preserve; it is unused state.
- `VoiceSessionPresence`/`VoicePresenceState`'s presence-strip UI is exported but **not imported anywhere in production** (`voice-session-presence.tsx:155` is unwired) — only its `VoicePresenceState` *type* is consumed elsewhere.

### A5. ⚠️ The single most important finding: `AppShell` is per-page, not root-level

Directly verified (not delegated): **`app/layout.tsx` contains only data/context providers** (`AuthProvider`, `OrgSyncBootstrap`, `EnterpriseBrandingProvider`, `EntitlementsProvider`, `UserProfileProvider`, `NotificationProvider`, `OnboardingProvider`, `ViewModeProvider`, `ThemeProvider`, `Toaster` — `apps/web/app/layout.tsx:86-111`). **`<AppShell>` itself is imported and instantiated independently by well over 100 individual `page.tsx` files** (confirmed via direct grep count across `apps/web/app`), including both `apps/web/app/ai/page.tsx` and `apps/web/app/agents/[id]/chat/page.tsx`.

**Consequence:** today, navigating between any two top-level routes (e.g. `/ai` → `/agents/42`) fully unmounts the entire app chrome — `Sidebar`, `TopBar`, `MobileBottomNav`, `CommandPalette`, `MesonToolbarPopup` — *and* any chat state local to that page's React tree. The continuity a user experiences today across page loads on `/ai` is **entirely due to localStorage/sessionStorage/server rehydration on remount**, not live in-memory continuity. If a user starts a voice turn on `/ai` and navigates to `/agents/42` mid-response today, that in-flight state is gone (though the eventual assistant message may still persist server-side and rehydrate on return).

This is precisely why the governing spec's requirement ("no reload, no duplicate agent, no new thread simply because presentation mode changes," §1, §15) is a **real architectural change**, not a CSS wrapper around the existing `AiWorkspace`. **Any runtime state that must survive route navigation has to be lifted above every per-page `AppShell` instance — i.e., into `app/layout.tsx` itself.** This single fact drives nearly every decision in Part B.

### A6. Existing shared components (spec §42 voice state; also feeds §20)

Single source of truth: `apps/web/components/gravitre/assistant/voice-presentation.tsx` (enforced by `scripts/check-chat-surface-drift.mjs` — no forks permitted).

| Component | Props | States |
|---|---|---|
| `GravitreWave` (= `GravitreVoiceWaveform`) | `speaker`, `compact?`, `active?`, `levels?` | speaker (user/agent) × active/idle — no explicit executing/success/error |
| `GravitreOrb` | `speaker`, `amplitude?` | speaker × reactive/keyframe pulse — no idle/listening/thinking labels itself |
| `VoiceStateVisualizer` | `state: VoicePresenceState`, `levels?` | `idle \| listening \| understanding \| thinking \| speaking \| interrupted \| disconnected \| error` — `idle`/`error`/`disconnected` render nothing (`null`) |

**Gap for the spec's Helper states (§19, §2):** the existing `VoicePresenceState` union has no `executing` or `working` state and no `needs_approval` state — those are chat-level concepts (`pendingTask`/`dialogueMode`), not voice states. The Helper's full state set (READY/LISTENING/THINKING/WORKING/EXECUTING/NEEDS APPROVAL/COMPLETE/ERROR) will need a **new, superset state model** that composes voice presence + tool/approval state, rather than reusing `VoicePresenceState` directly.

### A7. Existing icon systems (spec §42, feeds §18)

Icons are **currently mixed**, not unified, across three+ layers:

1. **`lib/icons.tsx`** — the app's main `<Icon name=".../>` wrapper, built on **lucide-react**, ~750 lines, dozens of names.
2. **`components/icons/nucleo/semantic.tsx`** — a newer, **14-icon** Nucleo set (`NucleoAgent`, `NucleoConnector`, `NucleoIntelligence`, `NucleoVoice`, `NucleoApproval`, `NucleoWorkflow`, `NucleoArrowRight`, `NucleoMenu`, `NucleoChevronDown`, `NucleoClose`, `NucleoBell`, `NucleoCommand`, `NucleoSearch`, `NucleoActivity`), partially overridden into `lib/icons.tsx` for ~20 names (`587-613`).
3. **`components/ui/nucleo-icon.tsx`** — a raw sprite loader (`<NucleoIcon id="…">`) against a 1000+ SVG library in `public/icons/nucleo/`, largely unused by name in product surfaces today.
4. **`components/icons/nodus-nav/outline.tsx`** — a third, separate hand-drawn glyph set used only for sidebar nav.

Concretely, `apps/web/components/runs/approval-batch-panel.tsx` imports raw `lucide-react` icons directly (`CheckCircle`, `Loader2`, `XCircle`) — confirming icon-family mixing is already normal practice in the codebase, not an edge case.

### A8. Existing design tokens (spec §42, feeds §16–17)

Source of truth: `apps/web/app/globals.css` (`:root`/`@theme`, Tailwind v4) + `apps/web/lib/design-system.ts` (TS aliases). **Directly verified, not guessed:**

| Token | Value | Semantic role (spec §17) |
|---|---|---|
| `--g-brand` | **`#16a374`** (`globals.css:62`, sourced from `gravitre-icon-green-1024.png`) | brand/active/selected/connected/success/verified |
| `--g-intelligence-surface` | `oklch(0.55 0.16 290)` — violet (`globals.css:211`) | intelligence/GIBE/reasoning |
| `--g-signal-surface` | `oklch(0.52 0.12 240)` — cyan/blue (`globals.css:227`) | signal/connectivity |
| `--g-approval-surface` | `oklch(0.72 0.14 75)` — amber (`globals.css:231`) | waiting/approval |
| `--g-danger` → `--destructive` | `oklch(0.55 0.22 25)` — red (`globals.css:104,233`) | critical/failed |
| `--g-surface-1/2/3` | `#ffffff` / `#f9f9f9` / `#f5f5f5` (`globals.css:195-197`) | mineral-white canvas |
| `--np-radius-sm/md/lg` | 6/8/12px; `--g-radius-panel` 16px (`globals.css:77-79,308`) | restrained radius scale |

**The exact 6-color semantic system the governing spec asks for (§17) already exists in the token layer, verbatim.** This redesign should *consume* these tokens, not invent parallel ones.

### A9. Reference-pattern analysis (spec §43)

| Reference | What's useful | What NOT to copy | Maps to Gravitre |
|---|---|---|---|
| **assistant-ui `AssistantModalPrimitive`** | Headless `Root`/`Anchor`/`Trigger`/`Content` separation; portal rendering; `data-[state=open/closed]` animation hooks; `portalProps.container` for a custom portal target | Built on **Radix Popover**, which is anchor-relative-positioned — wrong model for a window that must free-drag anywhere and remember arbitrary x/y. Generic bot-icon/rounded-bubble look is exactly the "customer-support widget" aesthetic §16 forbids. | Adopt the *headless composition pattern* (`GravitreAIWorkspaceProvider` + explicit `Helper`/`Content` slots), but implement our own `fixed`-positioned, draggable Content — not Radix-Popover-anchored. |
| **CopilotKit `CopilotPopup`** | One shared chat engine (`CopilotChat`) driving Popup/Sidebar/inline via different shells; slot-override system (component / className / partial-props per slot) | `clickOutsideToClose` defaults `true` — directly contradicts §4 (no click-outside dismiss). Generic "modalHeaderTitle" framing reads as support-widget, not an agentic workspace with tool calls/voice/approvals. | The "one core engine, N presentation shells" split is *exactly* our target internal split (`GravitreAIConversation` core + `GravitreFloatingWorkspace`/`GravitreAIWorkspaceShell`/`GravitreAIMobileSheet` shells). |
| **shadcn "AI Chat Floating Widget" block** | Concrete baseline numbers (460px panel, scale-up entrance, typing indicator, per-message copy/feedback actions) | Explicitly marketed for "customer support widgets... embedded help desk chatbots"; single fixed size; **no** resize/drag/expand/fullscreen at all — doesn't address 3 of our 4 required states. | Use only as a sanity check on baseline sizing/animation-duration numbers, not as a structural or visual reference. |
| **Nodus Agent Template (aceternity)** | Confirms the stack this codebase already adopted (Next 15/React 19/Tailwind 4/motion-for-react) | The public template page is a paid/gated marketing page with no deep component detail exposed | **Not a new reference to derive from — it's already the live token set.** `globals.css` / `lib/design-system.ts` (§A8 above) *is* the operative "Nodus × Gravitre" visual language today. Consume those tokens directly. |

---

## PART B — PROPOSED ARCHITECTURE (spec §53 items 6–15)

### B1. Proposed floating-window architecture (item 6)

**Core principle, driven directly by finding A5:** one persistent runtime, mounted exactly once, at the true application root — never inside a per-page `AppShell`.

```
app/layout.tsx  (mounted once, ever, for the whole app session)
└── <GravitreAIWorkspaceProvider>          ← owns ALL chat/voice/tool/approval/window state
      {children}                          ← existing per-page <AppShell> tree, unchanged
      <GravitreAIPresentationRoot />       ← portal target, rendered once, ALWAYS present
            ├── GravitreAIHelper           (presentationMode === "helper")
            ├── GravitreFloatingWorkspace  (presentationMode === "float")
            ├── GravitreAIWorkspaceShell   (presentationMode === "expanded" | "fullscreen")
            └── GravitreAIMobileSheet      (mobile equivalent, same modes, vaul-based)
```

Because this subtree lives above every page's own `<AppShell>`, it is **structurally immune** to the per-page remount behavior in A5 — navigating from `/ai` to `/connectors/42` never touches it.

**Not a modal, by construction:** `GravitreFloatingWorkspace`'s content uses `position: fixed` only — no `Radix Dialog`/`AlertDialog` wrapper, no backdrop, no default focus trap. Only `GravitreAIWorkspaceShell` in *fullscreen* mode adopts dialog-like semantics (see B9 Accessibility), since at that point there is genuinely nothing else on screen to interact with.

### B2. Proposed component architecture (item 7)

| Proposed component | Maps to existing | New work required |
|---|---|---|
| `GravitreAIWorkspaceProvider` | **New.** Hoists today's per-page `useChat`/voice/thread state out of `AiWorkspace`/`AgentChatPage` | New context; extraction, not rewrite |
| `GravitreAIConversation` | = today's `ChatTranscript` + `SharedChatComposerControls`, made shell-agnostic | Refactor: remove any layout assumptions tied to full-page `/ai` (e.g. viewport-height math) |
| `GravitreAILeftPanel` | = existing `ConversationSidebar`, reused as-is | none |
| `GravitreAIRightPanel` | = existing `LiveActivityRail` + `TaskSidePanel`, composed into one panel | Minor consolidation — today these are two separate surfaces (rail + inline sub-panel) |
| `GravitreAIHelper` | **New** | Reuses `GravitreOrb`/`VoiceStateVisualizer`, `NucleoAgent` |
| `GravitreFloatingWorkspace` | **New shell** | Hosts `GravitreAIConversation` unmodified where possible |
| `GravitreAIWindowHeader` / `GravitreAIWindowControls` | **New** | Nucleo icon controls (see C1 for gaps) |
| `GravitreAIWorkspaceShell` | **New shell** (serves both Expanded and Fullscreen) | Composes Left + `GravitreAIConversation` + Right |
| `GravitreAIContextDrawer` | **New** | Slide-over for secondary info in small/medium Float widths (spec §7, §13) |
| `GravitreAIMobileSheet` | **New** | Built on **`vaul`** (already an installed dependency, confirmed zero current app usage) |

**Required refactor, called out explicitly:** `AiWorkspace` and `AgentChatPage` currently each instantiate their own `useChat`, voice hooks, and persistence independently (A2). Both must be migrated to consume `GravitreAIWorkspaceProvider`/`GravitreAIConversation` rather than duplicating. This refactor is also the natural point to resolve the approvals/execution-panel/file-picker gap between the two surfaces found in A3 — **flagged as a decision, not decided here:** should the unified `GravitreAIConversation` bring approvals/execution/file-picker to agent-scoped chat too (parity), or should that remain an intentional, product-owned scope difference? Silently picking one during the refactor would be exactly the kind of undisclosed decision this program's standing rules warn against.

### B3. Proposed state-management approach (item 8)

**Recommendation: extend the existing pattern (React Context + SWR + `useChat`), do not introduce Redux/Zustand.** This matches spec §38 ("wrap the existing system, don't duplicate state") and the fact that no global store exists anywhere in chat today (A4).

`GravitreAIWorkspaceProvider` exposes:
- `presentationMode: "helper" | "float" | "expanded" | "fullscreen"` + setter, session-persisted, viewport-clamped on restore (spec §5)
- `conversation` — today's `useChat` instance + thread/message state, hoisted verbatim
- `voice` — existing `useVoiceDuplexSession`/`useAgentVoicePlayback` instances, hoisted
- `toolState`, `approvalState` (today's `pendingTask`/`dialogueMode`/`executionGate`), hoisted
- **`pageContext` — genuinely new.** Today, nothing captures "what page/object the user is on" (A4). A lightweight `usePageContext()` hook (`usePathname()` + route params) must be added, kept **explicitly separate** from `conversation` state, so navigation only updates "current UI context" and never silently mutates conversation history — directly satisfying spec §15's distinction between CONVERSATION CONTEXT and CURRENT UI CONTEXT.
- Window geometry (position/size per mode), clamped to viewport, session-persisted

### B4. Proposed portal/z-index architecture (item 9)

Existing z-index tiers (directly audited): `z-50` app-wide default for Dialog/Sheet/Popover/Dropdown/Tooltip/`VoiceOrbTakeover`; `z-[70]` "elevated app chrome" (Meson panel, chat session dropdowns); `z-[100]` toasts; `z-[120]` marketing consent banner. **These are informal, one-off magic numbers today, not named tokens** — a real, pre-existing gap.

**Recommendation:** introduce one new, explicitly named tier, e.g. `--z-ai-workspace: 85`, documented in `globals.css` alongside the existing scale:

```
z-50   → modals, popovers, VoiceOrbTakeover        (existing)
z-70   → app chrome overlays (Meson panel, etc.)   (existing)
z-85   → Gravitre AI floating workspace + Helper   (NEW — proposed)
z-100  → toasts                                     (existing)
z-120  → consent banner                             (existing)
```

This sits above all app content, dropdowns, and the existing Meson/voice-orb layer, but below toasts and consent — so a toast notification is never trapped behind the floating AI window (a real risk if we reused `z-50` or `z-[70]` as-is, since `VoiceOrbTakeover` already occupies `z-50`).

### B5. Drag/resize implementation recommendation (item 10)

- **Drag:** use `framer-motion`'s native `drag` prop (already a dependency, v12 — confirmed installed) with `dragConstraints` computed from viewport bounds, `dragElastic={0}`, `dragMomentum={false}` for a "physical, calm, precise" feel with no bounce/overshoot. `dragListener={false}` on the window root + `dragControls` triggered only from pointer-down on the header region — this is how §22's "use the header as the primary drag zone, don't interfere with buttons/text-selection/inputs" gets enforced structurally, not by convention.
- **Resize:** **no dedicated resize library is installed today** (`react-rnd`, `@dnd-kit/*` both confirmed absent). **Recommendation, flagged as a real decision:** build a small custom `useWindowResize` pointer-event hook (clamped to the min/max dimensions in spec §23) rather than adding `react-rnd` as a new dependency — keeps one library (`framer-motion`) doing both drag and resize-handle dragging, consistent with this program's general preference for minimal new dependencies. The trade-off: `react-rnd` is more feature-complete out of the box at the cost of a new dependency; the custom hook is less bundle weight but is new code requiring its own tests. **This needs your sign-off before Phase 1**, not a unilateral pick.
- `react-resizable-panels` (already installed, confirmed **zero usage anywhere in the app today**) is the right existing fit for the *internal* Left/Right panel-width dragging inside Expanded/Fullscreen — a different problem from outer-window resize, but a ready, unused match worth using.

### B6. Responsive behavior plan (item 11)

Spec §13 requires breakpoints tied to the **AI window's own width**, not the browser viewport — Tailwind's viewport-based media queries cannot express this. Recommendation: a `ResizeObserver`-backed `useElementWidth(ref)` hook driving three internal content tiers, independent of the four presentation-mode tiers:

| Internal tier | Width | Content |
|---|---|---|
| Small Float | <440px | Conversation only, compact header, minimal action rail |
| Medium Float | 440–620px | + richer tool/execution state, optional `GravitreAIContextDrawer` |
| Large Float | >620px | + optional narrow context panel |
| Expanded/Fullscreen | n/a (mode, not width) | Left + Center + Right |

### B7. Mobile behavior plan (item 12/29)

- Use **`vaul`** (installed, currently zero app usage — a genuinely ready, unused dependency) for Helper → BottomSheet → ExpandedSheet (snap point) → Fullscreen. Reuses the *same* `GravitreAIConversation` core; only the outer shell (`GravitreAIMobileSheet` vs. `GravitreFloatingWorkspace`) swaps — consistent with "one runtime, multiple presentation modes."
- The existing `md` breakpoint (768px) already governs `MobileBottomNav`, `ConversationSidebar`'s drawer mode, and `LiveActivityRail`'s drawer mode (A-series audit) — reuse it as the desktop↔mobile-sheet cutover rather than inventing a new one.
- **Concrete collision to solve:** `MobileBottomNav` is `fixed inset-x-0 bottom-0 z-30 h-14` with safe-area padding (`mobile-bottom-nav.tsx:33`), and mobile already treats "Chat" as one of its 5 nav items linking to `/ai` (`mobile-bottom-nav.tsx:16`). The bottom-left Helper must sit *above* that bar with an explicit offset (e.g. `bottom: calc(56px + env(safe-area-inset-bottom) + 12px)`), and — separately, a real product question, not decided here — **should the mobile bottom-nav's existing "Chat" item still deep-link to the full `/ai` page, or should it now open the Helper's floating/sheet workspace instead?** Both are defensible; this needs a call.

### B8. Desktop OS behavior recommendation (item 13/31)

**Directly confirmed:** `apps/desktop` is a **separate Tauri v2 codebase** that *already* implements almost exactly the "persistent, always-on-top companion" concept — global hotkey (Alt/Option+Space), tray presence, chat (text/voice), native approvals (`apps/desktop/README.md`) — and does **not** reuse `AiWorkspace`/`ChatTranscript`/`SharedChatComposerControls` from `apps/web` at all; it has its own minimal chat UI (`apps/desktop/src/App.tsx`).

**Recommendation:** treat the web Floating Workspace and the Tauri companion as two different, complementary surfaces (browser tab vs. native OS companion) for this phase — do **not** attempt to converge them now. Converging them (e.g. having Tauri render the same React shell) is a real, separate, higher-effort initiative deserving its own dedicated decision, not something to fold into a UI presentation redesign. Per spec §31's own instruction, no OS-level window behavior is proposed for the web app until this is confirmed.

**Browser extension** (`apps/extension`, Manifest V3 — directly confirmed): already ships **both** a popup *and* a native Chrome `sidePanel` (`manifest.json: side_panel.default_path: sidepanel.html`). The Helper→expanded mental model maps cleanly onto popup→sidePanel already, with no new browser API needed — this is lower-risk than the desktop question and can reuse the extension's existing side-panel surface once the web workspace's core is extracted.

### B9. Accessibility plan (item 23/34/35)

- **Float mode:** `region`/`complementary` landmark, `aria-label="Gravitre AI"` — explicitly **not** `role="dialog"`, no focus trap (spec §34's own constraint: this is not a blocking modal).
- **Fullscreen mode:** `role="dialog"` `aria-modal="true"` **with** a focus trap — the only mode where trapping is actually correct, since nothing else is visibly interactive at that point.
- Escape closes Fullscreen → previous mode, but does **not** close Float (Float has no modal semantics to escape from).
- Resize handles get keyboard-operable equivalents (arrow-key step-resize on a focusable handle), not mouse-only.
- Reduced motion: reuse the existing `useMotionPrefs()`/`useReducedMotion()` convention already used elsewhere in chat (`gravitre-chat-avatar.tsx`, `voice-session-presence.tsx`) — do not reinvent.
- Presentation-mode changes and new-message arrival get an `aria-live` announcement, following the existing pattern in `voice-session-presence.tsx`.

### B10. Performance plan (item 24/37)

- No remount by construction (single portal-mounted subtree per B1) — this is the biggest win and comes for free from the architecture, not from optimization work.
- Drag via `framer-motion`'s transform-based `drag` (GPU-composited, no layout thrash); resize-handle pointer deltas throttled to `requestAnimationFrame`, not per-pixel `setState`.
- Secondary panels (`GravitreAIRightPanel` contents) lazy-mounted only when Expanded/Fullscreen + open — never pre-mounted while in Float.
- Measurement plan: drag FPS, resize responsiveness, and memory measured against the **Phase 0 isolated prototype** (below) via the browser CDP `Profiler` tooling already available in this environment, *before* any stateful production refactor — so a performance problem is caught in isolation, not discovered after Phase 1 ships.

---

## PART C — ICON MAP, TOKEN MAP, PROTOTYPE PLAN, PHASING (items 14, 15, 16–22, 25)

### C1. Nucleo icon map (item 14)

| Affordance needed | Status today | Recommendation |
|---|---|---|
| Close | ✅ `NucleoClose` exists | Reuse directly |
| Search | ✅ `NucleoSearch` exists | Reuse directly |
| Voice | ✅ `NucleoVoice` (`WaveformLinesOutline24`) exists | Reuse directly |
| Approval | ✅ `NucleoApproval` exists | Reuse directly |
| Expand/Collapse/Minimize/Fullscreen | ❌ Nucleo has none (only Lucide `Maximize2`/`Minimize2` today) | **Port** — 4 new Nucleo glyphs |
| Drag handle | ❌ Missing everywhere except one Lucide `GripVerticalIcon` in `components/ui/resizable.tsx` | **Port**, or explicitly accept one Lucide exception for this single low-visibility affordance — flagged as a decision |
| Mic | ❌ Lucide `Mic` only | Port |
| Attach | ❌ Missing entirely, both icon systems | Port |
| Send | ❌ Lucide `Send`/`ArrowUp` only | Port |
| Run / Execution | ❌ Lucide `Play`/`Zap` only | Port |
| Success / Error | ❌ Lucide `CheckCircle`/`XCircle` only | Port |
| Settings | ❌ Lucide `Settings` only (sidebar has a different-family `NavSliders`) | Port |
| History | ❌ Lucide `History` only | Port |
| New chat | ❌ Lucide `MessageCircle`/`Plus` only | Port |
| Panel toggle | ❌ Lucide `PanelLeft`/`PanelRight` only | Port |

**Net: ~11 of 18 needed affordance icons require new Nucleo assets** sourced and ported into `components/icons/nucleo/` (following the existing `<Name>Outline24.tsx` + `semantic.tsx` registry pattern) before this workspace can be "maximally Nucleo" (spec §18) without mixing icon families as badly as the rest of the app already does. This is real, boundable work — flagging so it's budgeted into Phase 0/1, not discovered mid-build.

### C2. Nodus visual-token mapping (item 15)

Directly reuse, verbatim, from `apps/web/app/globals.css` / `apps/web/lib/design-system.ts` — **no new tokens invented**:

| Use | Token |
|---|---|
| Brand/active/selected/connected/success | `--g-brand` `#16a374`, `--g-brand-soft` `#e0f3ec` |
| Intelligence/GIBE | `--g-intelligence-surface` (violet, `oklch(0.55 0.16 290)`) |
| Signal/connectivity | `--g-signal-surface` (cyan, `oklch(0.52 0.12 240)`) |
| Waiting/approval | `--g-approval-surface` (amber, `oklch(0.72 0.14 75)`) |
| Critical/failed | `--g-danger` → `--destructive` (red, `oklch(0.55 0.22 25)`) |
| Canvas | `--g-surface-1/2/3` (`#ffffff`/`#f9f9f9`/`#f5f5f5`) |
| Workspace shell radius | `--g-radius-panel` (16px) |
| Control/field radius | `--np-radius-md`/`--np-radius-lg` (8/12px) |
| Elevation | `--g-shadow-*` / `--elevation-1..4` |
| Type | `--g-type-*` scale + Inter Display (`--font-primary`) |
| Motion | `MOTION` constants (`lib/design-system.ts`) + spring values already used for chat entrances (`stiffness: 380, damping: 32`, `lib/animations.ts:606-614`) |

### C3. Prototype plan (items 16–20) — proposed as **Phase 0**, not yet built

Building and screenshotting four real, high-fidelity, interactive states at 6 breakpoints is itself substantial implementation work. The honest plan: build them as real React components, but **fully isolated from production** — a new route not linked from any nav, not indexed, not wired to real conversation state (mock/static transcript data only), so nothing here can be mistaken for a shipped surface:

- New route, e.g. `apps/web/app/dev/ai-workspace-preview/page.tsx` — no sidebar entry, no `sitemap` inclusion.
- Builds `GravitreAIHelper` (4 states: READY/THINKING/NEEDS APPROVAL/COMPLETE), `GravitreFloatingWorkspace`, `GravitreAIWorkspaceShell` (Expanded + Fullscreen), `GravitreAIMobileSheet` — using real Nodus tokens (C2) and whatever Nucleo icons exist today, with Lucide fallbacks for the confirmed gaps in C1 clearly acceptable at prototype stage.
- Demonstrates all 5 transitions (Helper→Float→Expanded→Fullscreen→Expanded→Float→Helper) with real Motion, against **mock** conversation/tool/approval data.
- Screenshotted at the 6 required breakpoints (1440/1728 desktop, 1024/768 tablet, 430/390 mobile) for your review.
- Zero production route/component changes in this phase.

### C4. State-preservation proof (item 21) — how it will be demonstrated

Because `GravitreAIWorkspaceProvider` mounts exactly once in `app/layout.tsx` (B1) — never remounted by route changes, per finding A5 — the same `useChat` instance, voice session, and thread id persist *by construction* across Helper↔Float↔Expanded↔Fullscreen transitions and across arbitrary route navigation. Proof plan: a mutation-proof test asserting the provider's React instance identity (a mount-counter ref) is unchanged across simulated route pushes in a test harness, plus a manual QA script — start a voice turn in Float, navigate to a different page mid-response, confirm the response completes and is present when reopened.

### C5. Underlying-app interaction proof (item 22)

Because Float mode uses no backdrop and no focus trap (B1/B9 — confirmed no `Dialog`/`AlertDialog` wrapper), the app underneath is fully clickable by construction, not by careful CSS tuning. Proof plan: the exact scripted pass from spec §50 (open a workflow, click an agent, change a dashboard filter, inspect a connector, all while Float stays open) run via browser automation during Phase 2 verification, plus an automated E2E test asserting a background button's `onClick` fires while the floating window is open.

### C6. Exact implementation phases (item 25)

| Phase | Scope | Production risk |
|---|---|---|
| **0. Isolated prototypes** | Build the 4 states + transitions in a dev-only, unlinked route with mock data (C3). Screenshot at all 6 breakpoints for review. | **Zero** — no production route touched |
| **1. State-hoisting refactor** | Build `GravitreAIWorkspaceProvider`; extract `GravitreAIConversation` from `AiWorkspace`/`AgentChatPage` **without changing visible behavior** — both existing routes keep rendering exactly as today, now sourcing from the shared provider instead of local state. Pure refactor, verified by full regression battery + no visual diff. | Low — behind existing routes, no new UI exposed |
| **2. Mount + Float, behind a flag** | Mount provider + `GravitreAIHelper` at root layout; wire Float mode as a new entry point using the now-hoisted real conversation. **Decision needed:** does visiting `/ai` directly now open the same floating workspace in Expanded mode, or does the inline page remain a separate, valid entry point? Ship behind a flag, verify live before rollout. Also resolve Part D's collision before this phase. | Medium — first real production surface |
| **3. Expanded/Fullscreen shell** | Wire in `GravitreAILeftPanel`/`GravitreAIRightPanel` (reused as-is), drag/resize (B5), keyboard shortcut (audited against existing shortcuts first), full accessibility pass (B9). | Medium |
| **4. Mobile + icon-gap closure** | `GravitreAIMobileSheet` via `vaul`; port the ~11 missing Nucleo icons (C1); resolve the mobile bottom-nav "Chat" question (B7). | Medium |
| **5. Regression + human verification + rollout** | Full backend+frontend regression battery; this program's standing human-verification discipline applied to the *new* surface (not just voice); performance measurement (drag FPS, resize responsiveness, memory) against the Phase 0 baseline; staged rollout. | Gated on your sign-off |

---

## PART D — ⚠️ Concurrent-work collision found during this audit (must resolve before Phase 2)

While this audit was in progress, a **different, concurrent session** committed directly to `main`:

> commit `8523bc1f` — "feat(ui): combo stack finish, dashboard presets, floating AI helper" — "mount a secondary floating AI sheet that routes into `/ai`"

This added `apps/web/components/gravitre/floating-ai-workspace.tsx` (116 lines) and wired it into `apps/web/components/gravitre/app-shell.tsx`. Inspected directly — **it does not implement this spec.** It is a small, unrelated feature from a different workstream (the surrounding commits are all "Nodus dashboard fidelity" work: `sidebar-nucleo.tsx`, `pack-kpi-panel.tsx`, `dashboard/kpi-registry.ts`). Specifically:

- It's a `Sheet` (Radix, right-side slide-over) triggered by a **bottom-right** button (`fixed bottom-20 right-4 ... md:bottom-6 md:right-6`) — spec requires **bottom-left** (§2).
- It shows 4 static quick-prompt buttons, then does a **full `router.push()` to `/ai`** on any click — it does not carry conversation state, is not draggable/resizable, has no Expanded/Fullscreen mode, and is explicitly commented "Not a dominant dashboard CTA."
- It's mounted from `app-shell.tsx` — i.e. it is **per-page**, subject to exactly the remount problem in Finding A5, not hoisted to root `layout.tsx`.
- It's hidden on `/ai` itself (`if (onAiRoute) return null`).

**Why this matters:** it's small enough to not conflict at the code level, but it creates a real **product/UX collision**: shipping the actual `GravitreAIHelper` (bottom-left, persistent, stateful) alongside this existing bottom-right quick-launcher would mean two different "AI helper" buttons on screen at once. **This needs your call before Phase 2:**
1. Retire this component when `GravitreAIHelper` ships (clean replacement), or
2. Repurpose its `QUICK_PROMPTS` content as a feature *within* the new `GravitreAIHelper`/`GravitreFloatingWorkspace` (its quick-prompts idea is genuinely reusable), or
3. Keep both intentionally (not recommended — same visual role, different corner, will read as a bug).

---

## Open decisions requiring your call before Phase 1 (not decided unilaterally above)

1. **Approvals/execution-panel/file-picker parity** between `/ai` and `/agents/[id]/chat` when unified into one `GravitreAIConversation` (B2).
2. **Drag/resize library choice:** custom pointer-event hook (recommended) vs. adding `react-rnd` as a new dependency (B5).
3. **Mobile bottom-nav "Chat" item:** keep deep-linking to full `/ai`, or repoint to the Helper/floating workspace (B7)?
4. **Direct `/ai` visits post-launch:** keep as a standalone page, or auto-open the same floating workspace in Expanded mode (Phase 2)?
5. **Drag-handle icon:** port a new Nucleo glyph, or accept one Lucide exception (C1)?
6. **Part D collision:** retire, repurpose, or keep the existing bottom-right `FloatingAiWorkspace` quick-launcher?

---

**This document makes no production changes.** Awaiting approval to proceed to Phase 0 (isolated, unlinked prototypes only) as the next concrete step.

---

## Reassessment (2026-09-09) — Cesar re-ran the governing redesign prompt

**GSAP / marketing visual goldens (separate track):** done — `fd06a3b4` on `main`, Vercel production READY. Not part of this AI workspace redesign.

**Is the AI floating redesign “done”?** **No** as a live default UX. **Yes** as Phases 0–4 code in tree behind an opt-in flag.

### What shipped since the original STOP gate

| Phase | Outcome |
|---|---|
| **0** | `/dev/ai-workspace-preview` mock Helper/Float/Expanded/Fullscreen/mobile + transitions |
| **1–4** | Production components: `GravitreAIWorkspaceProvider`, `GravitreAIHelper`, `GravitreFloatingWorkspace`, `GravitreAIWorkspaceShell`, `GravitreAIMobileSheet`, bridges from `AiWorkspace`, shortcut Ctrl/Cmd+Shift+L, presence announcer, unit tests |
| **Flag** | `NEXT_PUBLIC_AI_FLOAT_ENABLED === "true"` — **default OFF**; embedded `/ai` remains the user-visible experience |
| **Part D** | Concurrent `floating-ai-workspace.tsx` bottom-right sheet — **removed** from tree (collision retired) |

### Remaining gaps vs governing prompt (Phase 5 / decisions)

1. **Cross-route continuity:** Helper still `router.push("/ai")` because live `useChat` is page-local — not overlay-any-route with one in-memory session.
2. **No session persistence** of float position/size/`presentationMode` (with viewport clamp on restore).
3. **Helper chrome** uses NucleoAgent + presence dot, not compact `GravitreOrb`.
4. **Window-width content tiers** (`useElementWidth` Small/Medium/Large Float) not implemented.
5. **Right panel** LiveActivityRail remains a fixed overlay compromise inside Expanded.
6. **`/agents/[id]/chat`** still outside the float/expanded/fullscreen path.
7. **Phase 5 rollout:** flag enable + prod human verification + performance measurement vs Phase 0 baseline — **not done**.

### Spec §53 items — status map

| Items | Status |
|---|---|
| 1–15 architecture / references / tokens / icons | Covered in this doc + reassessment; implementation largely matches proposal |
| 16–20 prototypes | Phase 0 route live for review |
| 21–22 continuity / underlying-app proofs | Partial on `/ai` + Float non-modal; full cross-route §50 unmet until hoist |
| 23–24 a11y / performance plans | Shells implement core a11y; measurement gated on Phase 5 |
| 25 phases | 0–4 code complete (flagged); **5 open** |

### STOP FOR APPROVAL (2026-09-09)

No further production AI-chat rewrite from the re-run of this prompt until Cesar chooses Phase 5 scope. Approval canvas: Cursor canvas `ai-float-workspace-approval`. Review prototypes at `/dev/ai-workspace-preview`.

**Open decisions (updated):** (1) when/where to enable the flag; (2) hoist `useChat` for true cross-route overlay; (3) `/ai` direct visit = embed vs auto-Expanded; (4) mobile nav Chat → `/ai` vs sheet; (5) agent-chat approvals/files parity; (6) persist window geometry; (7) Helper = NucleoAgent vs GravitreOrb.

---

## Phase 5 shipped (2026-09-09) — Cesar approved Phase 5

### Decisions applied

| Decision | Choice |
|---|---|
| Flag | **Default ON** (`NEXT_PUBLIC_AI_FLOAT_ENABLED !== "false"`); kill-switch `=false` |
| Cross-route overlay | Root-mounted `GravitreAIWorkspaceHost` (lazy-armed) — Helper/shortcut **no longer** `router.push("/ai")` |
| `/ai` direct visit | Full-page embed via portal slot when float closed; navigating **onto** `/ai` while float open collapses to full-page of same runtime |
| Mobile nav Chat | Unchanged → `/ai` (sheet still used when float opened from Helper on mobile) |
| Agent chat parity | Deferred — `/agents/[id]/chat` still separate `useChat` |
| Window geometry | **sessionStorage** persist size + drag translate with viewport clamp |
| Helper visual | Compact **GravitreOrb** when active (listening/thinking/executing/working); NucleoAgent when idle |

### Code

- `components/gravitre/ai-workspace-host.tsx` — lazy-armed single `AiWorkspace`
- `components/gravitre/ai-full-page-slot.tsx` — portal target on `/ai`
- `lib/ai-float-geometry.ts` + Float shell persistence
- `hooks/use-element-width.ts` — Float content tiers (small/medium/large)
- Helper/shortcut updated; flag polarity flipped for rollout

### Evidence (unit)

Run: `pnpm --filter @gravitre/web exec vitest run __tests__/gravitre/ai-workspace-flags.test.ts __tests__/gravitre/ai-helper.test.ts __tests__/gravitre/use-gravitre-ai-shortcut.test.ts __tests__/gravitre/ai-float-geometry.test.ts`

### Still open / not claimed PASS in prod

- Human verify Helper → Float on `/dashboard` without route change, mid-stream navigate, reopen
- Drag FPS / memory vs Phase 0 baseline
- `/agents/[id]/chat` unification
- Mobile bottom-nav Chat → sheet (explicit product call still available)

---

## Open decision #4 resolved (2026-09-09) — direct `/ai` visits

Cesar reported the live `/ai` page still looked like the pre-redesign
full-page embed. That was Phase 5's disclosed, intentional behavior (see
"Decisions applied" above: `/ai` direct visit = full-page embed via portal
slot when float closed), not a bug — but re-presented as a choice once Cesar
saw it live, since Open decision #4 above was explicitly never resolved
unilaterally.

**Choice made:** a direct `/ai` visit now auto-opens the Expanded shell —
the same window chrome reached from any other page's Helper → Float →
Expand — instead of staying a plain full-page embed. Explicitly closing the
shell (or navigating there after an explicit close, this session) still
falls back to the pre-Phase-5 full-page embed.

**Code:** `components/gravitre/ai-workspace-provider.tsx` — a `useEffect`,
gated on `GRAVITRE_AI_FLOAT_ENABLED` and an `explicitlyClosedRef` (so an
explicit close sticks for the session), auto-sets `floatWorkspaceOpen=true` /
`presentationMode="expanded"` on a direct `/ai` (or `/ai/*`) visit.

**Evidence (unit):** `pnpm --filter @gravitre/web exec vitest run __tests__/gravitre/ai-workspace-provider.test.ts __tests__/gravitre/use-gravitre-ai-shortcut.test.ts` — 11 + 5 tests passing, including the new "auto-opens on direct /ai visit", "does NOT auto-open on non-/ai route", and "explicit close sticks for the session" cases.

**Not yet PASS in prod:** requires merge → Railway/Vercel redeploy → live
`/ai` reload in an authenticated session before this can be marked done per
the evidence-linked PASS bar.

### PASS (2026-09-09, ~15:40 PT)

Cesar reloaded `https://gravitre.app/ai` in his own authenticated session
post-deploy and confirmed: "it works." Deployed commit: `fd4042f1`
(merge of `f58ecb3d`), Vercel deployment `dpl_J5Z3krgKRDGNDkrAunv3MMYKr6UX`,
state `READY`, target `production`. This closes the "Not yet PASS in prod"
gap above — direct `/ai` visits now open the Expanded shell, verified live
by the product owner, not just unit-tested.

# Gravitre UX/UI 3.0 Plus — Cesar Approval Package (Revised)

**Date:** 2026-09-20  
**Status:** Planning baseline accepted · **Broad production rollout NOT approved**  
**Gate:** STOP FOR CESAR'S HARNESS REVIEW before any production slice

---

## Cesar design selection (2026-09-20 — locked)

| Decision | Selection |
|----------|-----------|
| Reset 2.0 closure | Three categories accepted — remains open |
| Intelligence | **I1 Field Topology** + collapsible **I2 change stream** (field primary) |
| Activity | **A1 TRACE Rail + Story** + optional **A2 timeline** |
| Navigation | **B Expandable labeled rail** (click/pin; no hover-only expand) |
| First pilot | **Activity A1** — after harness approval |
| Journey tests | Staging first → controlled prod smoke |
| Harness | `/dev/ai-workspace-preview?s=foundation\|intelligence\|activity\|navigation` |

See `docs/design/GRAVITRE_3.0_HARNESS_REVIEW.md` for review steps.

---

## Executive summary

Planning direction is approved. This package revises the dependency sequence per Cesar amendments:

1. Close Reset 2.0 **honestly** (defects vs proof gaps vs visual debt).
2. Establish **shared 3.0 Plus visual foundation** in the design harness.
3. Prototype **Intelligence** and **Activity** as complementary signature surfaces (3 concepts each).
4. Prove shared grammar between them (not two unrelated custom apps).
5. Audit global shell **before** changing it.
6. Select **one** controlled production pilot after design selection.

**Objective:** Make Gravitre's intelligence and execution **understandable** through a distinctive, coherent interface — not merely more visually sophisticated.

---

## 1. Reset 2.0 closure plan

Reset 2.0 remains **open**. Remaining work is split into three categories. Moving items into 3.0 Plus does **not** mark Reset 2.0 complete.

### A. Functional or architectural defects

Fix without waiting for visual redesign.

| Item | Problem | Evidence | Action | Owner gate |
|------|---------|----------|--------|------------|
| Orphan Ask entry | Dead or duplicate summon path | `ask-gravitre-entry.tsx` exists; superseded by `AskGravitreSummonButton` | Delete or wire to canonical summon | Engineering — no design gate |
| Legacy redirect confusion | `/runs`, `/outcomes`, `/integrations` still resolve | `app-routes.ts`, `sidebar-nav-config.ts` active matchers | Keep redirects; document in terminology; no UX change until nav audit | IA doc only |
| Intelligence agents redirect | `/intelligence/agents` → `/agents` | `app/intelligence/agents/page.tsx` | Correct architecture; verify deep links in journey test | Journey test |
| `layoutId` / presentation continuity | Possible broken morph edge cases | Phase 4 tests mock-only | Fix if journey test FAILs | Defect-only |
| Plan-hold / chat regressions | Backend ordering | CI cognitive suite (separate track) | Fix on evidence — not UX 3.0 | Engineering |

**Rule:** Ship defect fixes on `main` as isolated commits. Do not bundle with visual redesign.

### B. Unproven behavior (NOT PROVEN until live journey evidence)

Source inspection, Vitest, and harness Playwright are **not substitutes** for authenticated browser proof.

| Behavior | Current evidence | Required proof | Status |
|----------|------------------|----------------|--------|
| Layout morph compact↔expanded↔fullscreen | Phase 4 unit tests | Authenticated `/ai` session + screenshot/trace id | **NOT PROVEN** |
| Intelligence map + lens transform | `page-context` API tests, G8 verify script | Live tenant: lens switch + inspector + graph load | **NOT PROVEN** |
| Activity two-pane selection + detail | Component tests | Live outcomes/work-objects load, select, back, deep link | **NOT PROVEN** |
| Approvals approve → continue path | Phase 3 source | Live approval row + audit_events continuation | **NOT PROVEN** |
| Command palette discoverability | Source exists | Novice task: find Activity without palette | **NOT PROVEN** |
| Responsive 390–1728 authenticated | Harness matrix only | Per-route screenshot matrix on prod/staging | **NOT PROVEN** |
| Marketplace install flow | Phase M unit | Live install + installed route | **NOT PROVEN** |
| Connector model B discovery→manage | Phase 3 unit | Live connect + verify journey | **NOT PROVEN** |
| Playwright visual regression | Harness routes | Prod/staging routes post-pilot | **NOT PROVEN** |

**Rule:** Labels stay **NOT PROVEN** until journey script records PASS with request/run/audit id or timestamped artifact. No upgrade to PASS from code review alone.

### C. Visual or interaction debt (carried into 3.0 Plus)

Do **not** rush to finish under Reset 2.0 / old design language.

| Debt | Evidence | Reset 2.0 doc called it | 3.0 Plus owner |
|------|----------|-------------------------|----------------|
| Generic page template (icon tile + eyebrow + title + description) | 50+ routes use `GravitrePageHeader` | Partial | Page intro variants by job |
| Intelligence hub visually quiet vs runtime | `intelligence/page.tsx` + collapsed evidence sections | Partial | Intelligence Field concepts |
| Activity lacks formal TRACE stage rail | `activity/page.tsx` two-pane; `execution-timeline.tsx` partial grammar | Partial | Activity TRACE concepts |
| Sources card-in-card KPI grid | `sources/page.tsx` | NOT STARTED | Sources slice (post-pilot) |
| Connector/workflow detail card-heavy | `connectors/[id]`, `workflows/[id]` | NOT STARTED | Connectors/workflows slices |
| Nucleo in-context optical pass | ~28 Nucleo vs ~280+ Lucide sites | Partial | Nucleo 3.0 with foundation |
| Motion enforcement | ~150+ ad hoc Framer files | Partial | UI physics + lint convention |
| Command OS visual (chat-template) | `ai-workspace-shell.tsx` | Partial | AI workspace slice (post-signature) |
| Marketplace discovery object density | `marketplace/assets` | Complete source / insufficient visual | Marketplace slice |
| Shared Inspector primitive | Per-page copy gates | Pattern complete / primitive missing | Foundation + signature surfaces |

**Reset 2.0 closure verdict:** **Architecture and IA largely shipped; design objective and live proof open.** Visual debt explicitly transfers to 3.0 Plus.

---

## 2. Updated 3.0 Plus dependency sequence

```
Phase 0 — Reset 2.0 defect fixes only (no visual redesign)
    ↓
Phase 1 — Shared visual foundation (harness only)
    typography roles · canvas · grid · semantic color · depth · motion tokens · node/edge geometry
    ↓
Phase 2 — Signature prototypes (harness only)
    Intelligence × 3 concepts · Activity × 3 concepts
    each: desktop · mobile · selected · contextual AI · loading · empty · error · reduced-motion
    ↓
Phase 3 — Cesar design selection (GATE)
    pick Intelligence concept · pick Activity concept · confirm shared grammar
    ↓
Phase 4 — Global shell alternatives (harness only)
    icon rail vs expandable labeled rail · top bar audit as a system
    ↓
Phase 5 — Authenticated journey test (NOT PROVEN → PASS/FAIL matrix)
    ↓
Phase 6 — ONE controlled production pilot (exact scope doc'd below)
    ↓
Phase 7+ — Remaining surfaces per priority list (each prototype-gated)
```

**Removed from immediate sequence:** Independent production redesigns of Connectors detail, Sources, and Activity as three parallel projects.

**Added:** Foundation-first; Intelligence + Activity as grammar-establishing pair; single pilot after selection.

---

## 3. Shared Creative Experience / Product UI semantic mapping

**Source:** Creative Experience System Pilot 1 (`/about` — Departments Converge) + Phase 12 product grammar.

### Primitive mapping

| Creative primitive | Marketing implementation | Product extract | Product status | Must NOT import |
|--------------------|-------------------------|-----------------|----------------|-----------------|
| **Signal Trace** | `GravitreSignalPath` + `GravitreSignalPacket` — capsule on Bézier path | Directed stroke + progress; kind colors (signal/action/learn) | **Extract** — extend `TracePath` + event-driven progress | Autonomous loop timing; decorative sweep on static lists |
| **Relational Topology** | `topologyForCoreState()` + `GravitreIntelligenceCore` | Core geometry morphs by **real** `coreState` / lens | **Extract** — Intelligence map already has `useIntelligenceCoreState`; align geometry rules | Marketing 3×3 dept grid; spinning orb metaphor |
| **Relationship Trace** | `learnedEdges` session persistence in story | Permanent edge after verified learn — **real** relationship API edges | **Extract** — graph edge `state: learned \| active \| idle` | Browser-session `Set` as fake persistence |
| **Agent Node** | `GravitreAgentNode` (marketing capability tile) | Functional actor chip: role label + capability, not avatar face | **Separate product component** — fleet node + activity actor rows | Marketing orchestration scene node 1:1 |
| **Evidence Mark** | `GravitreEvidenceMark` tones: evidence / error / waiting | `EvidenceChip` re-export in `creative-grammar/` | **Shipped** — `execution-timeline.tsx`, `approvals/page.tsx` | Fixed marketing labels; invented confidence |

### Semantic color bridge (shared)

| Semantic | Creative token | Product CSS var | Use |
|----------|---------------|-----------------|-----|
| Verified / action | `#16a374` / `CREATIVE_BRAND` | `--g-emerald`, `--color-brand` | Success path, verified step |
| Intelligence / learn | violet mix | `--g-intelligence` | Inference, learning lens |
| Signal / connection | blue | `--g-signal` | Retrieval, connector hop |
| Waiting / approval | amber | `--g-approval` | Governed pause; path continues |
| Failure | error red | `--destructive` | Scoped branch failure |

### Motion bridge

| Creative | Product rule |
|----------|--------------|
| `CREATIVE_TOKENS.spring` (280/28) | Default spring for selection, inspector open |
| Transfer duration ~800–1100ms | **Event-driven only** — one beat per real state change |
| Path sweep gradient (2s loop) | **Marketing only** — product uses `TracePath` controlled progress |
| `useReducedMotion()` | Already in marketing + `TracePath`; mandatory on all new primitives |

### Data boundary

| Surface | Marketing | Product |
|---------|-----------|---------|
| Department network | `NETWORK_SCENARIOS` fixtures | `IntelligencePageContextResponse.graph` from `/api/intelligence/page-context` |
| Learned edges | Session `Set` in browser | `RelationshipRow` / canonical graph edges |
| Activity trace | Story beats | `BusinessOutcomeDto.sections.timeline`, `WorkObjectEventDto`, run audit events |
| Honesty caption | Required on `/about` | Only on empty/partial/stale data states — not on live populated views |

**Package path:** `apps/web/components/gravitre/creative-grammar/` (thin re-export) + new `apps/web/components/gravitre/visual/topology/` for shared node/edge primitives (harness first).

---

## 4. Three Intelligence concepts

Each concept uses **real data shapes** where available:

- `IntelligencePageContextResponse` — `snapshot`, `graph.nodes[]`, `graph.edges[]`, `activeLens`, `coreState`
- `MapNode` / `MapEdge` from `map-topology.ts`
- Fixtures: `lib/e2e-shot-fixtures.ts` relationship rows when API unavailable in harness

**Required states per concept:** desktop · mobile · selected object · contextual AI · loading · empty · error · reduced-motion

---

### Intelligence Concept I1 — **Field Topology** (evolution of current map)

**Structure:** Full-width canvas; lens bar transforms **one** shared topology (not five columns). Core hub morphs geometry per lens (`topologyForCoreState` rules adapted to real `coreState`). Satellites = departments, agents, signals from canonical graph.

**Hierarchy:** Canvas dominant (70%+ viewport height). Eyebrow + single-line title only — no description block. Inspector = right sheet (existing pattern). Evidence = inline on selected node, not collapsed page footer.

**Interaction:** Lens switch morphs node emphasis + edge states (200ms, shared spring). Select node → inspector + contextual Ask chip ("Explain this relationship"). Double-click node → focus neighborhood.

**Visual model:** Relational topology from creative system; mineral canvas; white work surface for graph; learned edges persist as brand hairline.

**Mobile:** Graph → focused node card + "Show connections" list; lens bar horizontal scroll; inspector = bottom sheet.

**Contextual AI:** Selection publishes `{ kind: "intelligence_node", id, lens }` — Ask chip in inspector header only.

**Loading:** Skeleton graph positions (no fake data); `deriveSnapshotLoadState` — no zero metrics flash.

**Empty:** "No graph yet" + honest setup actions; optional subtle grid structure (not decorative particles).

**Error:** Inline retry on canvas; partial graph if `qualityFlags` warn.

**Reduced motion:** Instant lens swap; static edge states; no packet animation.

**Novice:** Lens labels plain language ("What Gravitre knows" / "What changed" / …).  
**Expert:** Keyboard lens切换; dense inspector metadata tab.

---

### Intelligence Concept I2 — **Split Rail + Field**

**Structure:** Left rail (240px): **change stream** — chronological learns, predictions, signals (from `snapshot.learnings`, `predictions`, `signals`). Right: topology canvas showing selected stream item's neighborhood.

**Hierarchy:** Rail answers "what changed?"; canvas answers "how is it connected?" — different spatial layout, **same** node/edge grammar as I1.

**Interaction:** Rail item select → canvas focuses subgraph + TRACE path highlight from entity to core. Lens bar lives in rail header (filters stream type).

**Visual model:** Rail uses operational typography + `EvidenceChip` for source attribution; canvas shares I1 geometry tokens.

**Mobile:** Rail becomes top segmented control (Changes | Graph); graph full width below.

**Contextual AI:** Ask about selected rail item or canvas node — single entry in combined inspector footer.

**Loading / empty / error / reduced-motion:** Same rules as I1; rail shows skeleton rows.

**Differentiator vs I1:** Time-ordered narrative left; not lens-only transform. Better for "what changed recently" job.

---

### Intelligence Concept I3 — **Matrix Lens**

**Structure:** Rows = entity types (Agents, Sources, Connectors, Outcomes, Knowledge). Columns = lens dimensions (Knows, Learns, Predicts, Acts, Improves). Cell = density indicator + top signal. Selecting cell expands inline panel with mini-topology for that intersection.

**Hierarchy:** Table-like scanability for experts; progressive disclosure for novices (expand one cell at a time).

**Interaction:** Hover cell → preview count; click → expand panel with subgraph + inspector. No full-page graph until cell selected.

**Visual model:** Cells use semantic tint at low opacity (violet intelligence, cyan signal); expanded panel uses full topology grammar.

**Mobile:** Single column per entity type; swipe between lens tabs; cell → full-screen panel.

**Contextual AI:** Ask scoped to cell context ("Why is Sales · Predicts elevated?").

**Loading / empty / error / reduced-motion:** Standard table skeleton; empty cells show "—" not fake numbers.

**Differentiator vs I1/I2:** Operational density first; graph on demand. Best for expert scanning across domains.

---

## 5. Three Activity concepts

**Real data shapes:**

- `BusinessOutcomeDto` + `sections.timeline`, `sections.evidence`, `runId`
- `WorkObjectDto` + `WorkObjectEventDto[]`
- `grammarToneForStepStatus()` + `EvidenceChip`
- Run detail: `/runs/{id}?trace=1`

---

### Activity Concept A1 — **TRACE Rail + Story** (recommended grammar anchor)

**Structure:** Desktop three-column: (1) queue list 320px — unchanged role; (2) **vertical TRACE rail** — stages INTENT → PLAN → AGENT → TOOL → ACTION → RESULT → VERIFICATION → OUTCOME; (3) **story panel** — stage content, evidence, actor chips.

**Hierarchy:** Rail is persistent orientation; story panel is primary reading surface. List selection updates rail + story.

**Interaction:** Click stage → scroll story to section; failed stage pins red on rail only (prior stages stay verified green — creative failure-scoping rule). Approval waiting = amber segment; approve continues same `runId` path.

**Visual model:** `TracePath` horizontal connectors between rail nodes; `EvidenceChip` at verification; `ProductStage` composition optional wrapper.

**Mobile:** List → story with collapsible TRACE chip strip (horizontal scroll); stages tap to jump.

**Contextual AI:** "Why did this fail?" on failed stage; "Summarize outcome" on selection — inspector footer chip, not header duplicate.

**Loading / empty / error:** List skeleton; empty queue honest; story error with retry fetch events.

**Reduced motion:** Static rail states; no progress sweep.

**Differentiator:** Clearest execution explainability; extends Phase 12 grammar already shipped.

---

### Activity Concept A2 — **Stream Timeline**

**Structure:** Two-column: left list (narrower 280px); right = **horizontal timeline** — stages as nodes left-to-right with zoom scroll; selected stage detail below timeline.

**Hierarchy:** Timeline is hero; optimized for comparing stage duration and parallel branches.

**Interaction:** Drag timeline zoom; hover stage → tooltip with timestamp + actor; click → detail expand.

**Visual model:** Same node radius, stroke weights, semantic colors as A1 — **horizontal** trace geometry instead of vertical rail.

**Mobile:** Vertical timeline (top-to-bottom); list sheet overlay.

**Contextual AI:** Same as A1; scoped to timeline selection.

**Loading / empty / error / reduced-motion:** As A1.

**Differentiator vs A1:** Better for multi-branch / parallel tool calls; slightly higher complexity.

---

### Activity Concept A3 — **Observability Canvas**

**Structure:** Full-width trace canvas (similar to workflow builder aesthetic but read-only). List collapses to top filter chips. Canvas shows run graph from audit events; inspector drawer on node select.

**Hierarchy:** Power-user observability; list is filter not primary.

**Interaction:** Pan/zoom canvas; live pulse on running node (single `GravitreSignal` pulse — not marketing packet loop); failure stops trace at node.

**Visual model:** Shares topology node component with Intelligence; Activity uses execution-specific stage icons (Nucleo).

**Mobile:** Canvas → **path explorer** — focused node with prev/next along trace; no pinch-zoom requirement.

**Contextual AI:** Node selection → Ask about tool/action.

**Loading / empty / error / reduced-motion:** Canvas skeleton; static graph when reduced motion.

**Differentiator vs A1/A2:** Maximum topology visibility; highest dev cost; best for complex multi-agent runs.

---

## 6. Shared grammar demonstration (Intelligence + Activity)

Intelligence and Activity **must not** look like unrelated custom apps. Shared grammar:

### Typography & numeric treatment

| Role | Token | Intelligence use | Activity use |
|------|-------|------------------|--------------|
| Page title | `TYPE.pageTitle` | "Intelligence" | "Activity" |
| Object title | `TYPE.objectTitle` (new) | Selected node label | Outcome / work object title |
| Metadata | `TYPE.metadata` + tabular nums | `generatedAt`, confidence | Timestamps, run ids |
| Trace label | `TYPE.monoLabel` (DM Mono 11px) | Edge id, entity id | Stage id, tool name |
| Metric | `TYPE.metricValue` | Snapshot metrics in lens bar | Optional queue counts |

### Canvas, grid, depth

| Layer | Token | Both surfaces |
|-------|-------|---------------|
| App canvas | `--g-canvas` mineral tint | Behind all work |
| Work surface | `--g-surface-1` | Graph canvas / story panel |
| Selected | `--g-surface-active` | Selected row / node |
| Inspector | `--g-surface-1` + hairline border-l | Sheet / drawer |
| Grid | 12-col ≥1280; 8-col tablet | List widths: 320px (Activity), graph flex |

### Node, edge, path geometry

| Element | Spec | Shared component target |
|---------|------|-------------------------|
| Node radius | 8px rect / 50% circle for core | `GravitreTopologyNode` (harness) |
| Node stroke idle | 1.25px `--g-border-subtle` | CREATIVE `traceIdle` |
| Node stroke active | 1.75–2px semantic color | CREATIVE `traceActive` |
| Edge idle | 1px mineral | |
| Edge active | 2px + `TracePath` progress | |
| Edge learned | 1.75px brand hairline persistent | Relationship Trace semantics |
| Core hub | Morph layout per state — not spinner | Adapt `topologyForCoreState` rules to product states |

### Selection & focus

- Selection ring: 2px `--g-emerald` outside stroke; focus visible keyboard ring matches.
- List row selection (Activity) and graph node selection (Intelligence) use **same** `--g-surface-active` fill tint (primary/5).

### Evidence & confidence

- `EvidenceChip` only with **real** labels from data ("run outcome", "policy", "sources").
- Confidence: numeric % in metadata role when API provides; **never** invented TRAINED badges.

### Status & error language

| Tier | Presentation | Example |
|------|--------------|---------|
| Primary execution state | Rail/node semantic color | failed, running, verified |
| Secondary health | Muted metadata | "Last sync 2h ago" |
| Capability | Text label, no pill | "Requires connector" |
| Environment | Top bar only | Production / Sandbox |

### Inspector behavior

- Opens on explicit selection only (existing Reset 2.0 rule).
- Header: object title + primary action + Ask chip.
- Body: operational sections; trace/evidence inline.
- Mobile: bottom sheet, same content order.

### Motion timing & easing

- Spring default: stiffness 280, damping 28 (`CREATIVE_TOKENS.spring`).
- Lens/stage transition: 200ms opacity + layout; no page route animation.
- Running state: single pulse per node max; reduced-motion → static badge "Running".

### Nucleo icon semantics

- Intelligence: `NucleoIntelligence`, graph toolbar icons from semantic map.
- Activity: `NucleoActivity`, stage icons per TRACE step (not Lucide per-step).
- Size ladder: 16 inline, 20 row, 24 header — consistent both surfaces.

### Responsive transformations

| Breakpoint | Intelligence | Activity |
|------------|--------------|----------|
| ≥1280 | Full canvas + inspector sheet | List + rail + story |
| 768–1279 | Canvas + bottom inspector | List + story; rail horizontal |
| ≤430 | Node focus mode | List OR story; TRACE chips |

---

## 7. Global navigation alternatives

**Audit scope:** Left rail, top bar, workspace switcher, environment switcher, Admin/Lite, command palette, notifications, AI launcher — **as one system**.

### Current state (code)

- **Left rail:** 64px icon-only; tooltips; 14 primary items in 5 sections (`sidebar-nav-config.ts`).
- **Top bar:** Org switcher, environment, route title, `GlobalCommandBar`, Admin/Lite toggle, Meson trigger, notifications, profile (`top-bar.tsx`).
- **Mobile:** Bottom nav subset + hamburger.
- **Command palette:** Global ⌘K; complements but not required today.

### Findings

| Control | Job | Issue | Recommendation |
|---------|-----|-------|----------------|
| Icon rail | Primary wayfinding | First-time learnability weak | Prototype **Alt B** before prod change |
| Org switcher | Tenant context | Necessary | Keep; ensure label visible |
| Environment switcher | Sandbox/prod | Power user | Keep; consider moving to settings for Lite |
| Admin/Lite | Seat mode | Necessary | Keep; clarify in onboarding |
| Route title | Orientation | Duplicates sidebar | Keep on mobile; optional quiet desktop |
| Command bar | Search + commands | Good | Expand verbs in Phase 5; not primary nav |
| Meson trigger | Creative/build entry | Niche | Evaluate overflow menu |
| AI launcher | Summon workspace | Necessary | Single canonical entry |
| Notifications | Async attention | Necessary | Keep |

### Alternative A — **Current icon rail** (baseline)

- Pros: Maximum content width; familiar to existing users.
- Cons: Novice discovery poor; tooltip ≠ IA.

### Alternative B — **Expandable labeled rail** (recommended prototype)

- Default 64px icons; hover or pin expands to 200px with labels + section headers.
- Pros: Learnability + density; no permanent width loss.
- Cons: Animation care; pinned state persistence.

### Alternative C — **Hybrid compact rail**

- Icons + 4–6 char abbreviated labels at ≥1024px always visible.
- Pros: No interaction to learn names.
- Cons: Permanent 120px width; truncation ambiguity.

**Prototype in harness:** `/dev/ai-workspace-preview?s=nav&scene=icon|expand|hybrid` (new surface — harness only).

**Rule:** Do not simplify top bar by hiding nav labels while keeping icon-only rail — that shifts burden to command palette.

---

## 8. Authenticated journey test plan & current blockers

### Blockers

| Blocker | Status | Resolution |
|---------|--------|------------|
| No agent session in this planning run | **BLOCKED** | Use approved test account via existing secure config |
| Credentials in repo | **Forbidden** | Use env-based Playwright auth or manual session |
| Prod vs staging parity | Unknown | Confirm target environment with Cesar |

### Test configuration (no credentials in docs)

- Use existing e2e auth patterns if present (`e2e/` helpers, CI secrets).
- Record results in `docs/design/GRAVITRE_3.0_JOURNEY_RESULTS.md` (create on first run).
- Each journey: PASS | FAIL | BLOCKED | NOT PROVEN + evidence pointer.

### Journey matrix

| ID | Journey | Steps | Verify |
|----|---------|-------|--------|
| J1 | Login → Home | Auth → `/home` | Dashboard loads, nav visible |
| J2 | Home → AI | Open Chat | Workspace loads, morph states |
| J3 | Home → Agent → detail → chat | Roster → agent → run/chat | Context retained |
| J4 | Home → Workflow → create → run | List → builder → execute | Run appears in Activity |
| J5 | Home → Connector → connect → verify | Discovery → OAuth → health | Status updates |
| J6 | Home → Intelligence → lens switch | Overview → learns → predicts | Graph/insp. updates |
| J7 | Home → Activity → failure → evidence | Failures tab → detail → trace link | Stage + run id |
| J8 | Home → Approval → approve | Queue → approve | Continuation audit event |
| J9 | Home → Source → add | Sources → add flow | List updates |
| J10 | Home → Marketplace → install | Discover → install → installed | Route + state |
| J11 | Search / Command | ⌘K find Activity | Works without sidebar |
| J12 | Settings / Admin | Org, billing rows | No regression |
| J13 | Workspace switch | Switch org | Data refreshes |
| J14 | Environment switch | Sandbox ↔ prod | Banner/scope clear |
| J15 | Deep links | `/runs/[id]?trace=1`, `/intelligence/learning` | Load correct context |
| J16 | Back navigation | Inspector → back | No orphan state |
| J17 | Lite seat | Lite mode surfaces | Locked BUILD items |

### Per-journey questions (from brief)

Record answers in journey results doc: start clarity, label match, context loss, duplicate paths, dead ends, AI availability, error recovery.

**Current status:** All journeys **NOT PROVEN** (code-informed walkthrough only).

---

## 9. Recommended production pilot (after design selection)

### Precondition

Cesar selects:
- One Intelligence concept (I1, I2, or I3)
- One Activity concept (A1, A2, or A3)
- Shared foundation tokens approved from harness

### Recommended first pilot: **Activity Concept A1 — TRACE Rail + Story**

**Rationale:**

- Extends Phase 12 grammar already on `execution-timeline.tsx` and `EvidenceChip`.
- Two-pane Activity layout already production-ready — **lower risk** than Intelligence graph rewrite.
- Proves shared TRACE primitive usable by Intelligence later (evidence chain, outcome path).
- Clear user benefit: answers "where did it fail?" without ambiguous "View in Gravitre".

### Exact file and route scope

| Scope | Files |
|-------|-------|
| **Route** | `/activity` only (All + WorkObjects tabs; Failures tab optional phase 2) |
| Page | `apps/web/app/activity/page.tsx` |
| New components (harness first) | `apps/web/components/activity/trace-rail.tsx`, `trace-story-panel.tsx` |
| Shared primitives | `apps/web/components/gravitre/visual/topology/` (node, edge — if not exists) |
| Extend | `apps/web/components/runs/execution-timeline.tsx`, `creative-grammar/index.ts` |
| Tokens | `apps/web/app/globals.css` (--g-canvas, surface tokens if not already) |
| **Exclude** | Intelligence routes, connectors, sources, sidebar, top bar, settings |

### Change justification template (required per change)

| Change | Problem | Evidence | Interaction | Visual | User benefit | Test |
|--------|---------|----------|-------------|--------|--------------|------|
| TRACE rail | User cannot see failure stage at glance | Walkthrough §Activity; ambiguous trace link | Select outcome → rail highlights stage | Vertical semantic nodes + TracePath | Instant orientation | J7 PASS + screenshot |
| Remove duplicate Ask header | Duplicate AI entry | Walkthrough redundancy audit | Ask chip in story footer only | Single chip | Less noise | J7 + AI context publish test |

### Pilot success criteria

- J7 PASS with audit_events or run id evidence
- No regression on work object tab selection
- Responsive 390 + 1280 screenshots
- Reduced-motion: static rail PASS
- Lighthouse no significant LCP regression on `/activity`

### If Cesar selects Intelligence first instead

Scope: `/intelligence` overview only (`app/intelligence/page.tsx` + `OverviewLivingMap` subtree). Do not pilot sub-routes until overview PASS.

---

## 10. Explicit items that remain unchanged (until later gated slices)

| Area | Reason |
|------|--------|
| **Settings** (+ org, billing, enterprise) | Calm operational; no functional reason for topology graphics |
| **Auth / login / signup** | Stable; out of 3.0 scope |
| **Lite seat surfaces** (`/lite/*`) | Separate program; inherit shell only |
| **Workflow builder canvas** | Own signature slice; not bundled with Activity pilot |
| **Connectors detail + Sources** | Visual debt; post-pilot slices |
| **Marketplace discovery** | Heavy redesign; own slice |
| **Marketing pages** (`/about`, creative scenes) | Illustrative; no direct import |
| **Backend APIs** | UI projects consume existing contracts |
| **Single `useChat` architecture** | Reset 2.0 complete — preserve |
| **Admin sidebar item count (~14)** | IA complete — nav **presentation** may change, not destinations |
| **Billing / trial banners** | Functional |
| **Nucleo purge of Lucide** | Semantic migration only when touching a surface |

---

## Harness implementation plan (pre-selection)

Extend `/dev/ai-workspace-preview`:

```
?s=intelligence&scene=i1|i2|i3|loading|empty|error|mobile|selected|reduced
?s=activity&scene=a1|a2|a3|loading|empty|error|mobile|selected|reduced
?s=foundation&scene=type|color|canvas|nodes|motion
?s=nav&scene=icon|expand|hybrid
```

Use `IntelligencePageContextResponse` fixture from e2e shots + `BusinessOutcomeDto` fixtures for Activity.

**No production routes until Cesar design selection.**

---

## Approval checklist for Cesar

- [ ] Reset 2.0 closure categories accepted
- [ ] Dependency sequence accepted (foundation → dual prototypes → selection → one pilot)
- [ ] Creative → product mapping accepted
- [ ] Intelligence concept selection: I1 / I2 / I3
- [ ] Activity concept selection: A1 / A2 / A3
- [ ] Shared grammar accepted
- [ ] Navigation alternative for prototype: A / B / C
- [ ] First production pilot: Activity A1 (default) or alternate
- [ ] Journey test environment confirmed
- [ ] Unchanged list accepted

---

## Related documents

- `docs/design/GRAVITRE_UX_RESET_2.0_COMPLETION_AUDIT.md`
- `docs/design/GRAVITRE_3.0_PRODUCT_WALKTHROUGH.md`
- `docs/design/research/GRAVITRE_3.0_REFERENCE_LIBRARY.md`
- `docs/design/GRAVITRE_PRODUCT_VISUAL_SYSTEM_3.0_PLUS.md`
- `docs/design/GRAVITRE_INTERACTION_SYSTEM_3.0.md`
- `docs/design/gravitre-creative-product-ui-grammar.md`
- `docs/design/gravitre-creative-experience-system.md`

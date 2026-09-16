# Gravitre Intelligence Experience Rebuild — Design Specification

**Status:** APPROVED (revised 2026-09-13) — **DO NOT IMPLEMENT** until final sign-off on this revision  
**Date:** 2026-09-13  
**Revision:** 2 (product decisions locked)  
**Scope:** Full re-imagination of customer Intelligence surfaces  
**Preserved:** All existing routes, real data sources, backend semantics (G1 canonical state)

---

## Executive diagnosis

The current Intelligence product reads as **an admin dashboard with a decorative radial diagram**, not as **the operating view of one shared business brain**. Four independent failure modes drive that perception:

| Problem | Symptom today | User interpretation |
|---------|---------------|---------------------|
| **Graph UX broken** | Fixed radial layout, overlapping labels/nodes, no zoom/pan/drag/focus | “This is a static illustration, not a map I can think with.” |
| **Misleading load states** | Lens metrics show `0` then change to real values as APIs resolve | “The system changed its mind” |
| **IA overload** | Second full nav on Learning; Training carries three nav layers | “Internal org chart, not business questions” |
| **Visual inconsistency** | Performance/Reports/Models feel like separate SaaS modules; raw `INSUFFICIENT_DATA` | “Engineering output, not intelligence” |

**Product promise to prove visually:** *One AI brain coordinating agents, people, outcomes, and improvement* — not a collection of AI dashboards.

**Implementation gate:** No production UI changes until this document is committed and explicitly approved for I1 start. Prior G1–G8 canonical state work remains the data foundation.

---

## 1. Final information architecture

### 1.1 Primary navigation (single persistent bar — **7 tabs**)

All Intelligence routes share **one** top-level hub navigation — no second full-width menu on any child page.

| Tab | Route | Role |
|-----|-------|------|
| Overview | `/intelligence` | Living Intelligence Map |
| Learning | `/intelligence/learning` | What Gravitre learned (business) |
| Predictions | `/intelligence/predictive` | Forward-looking assertions + response |
| Performance | `/intelligence/performance` | Outcome attribution + business impact |
| Models | `/models` | Business intelligence catalog + usage |
| Model Studio | `/intelligence/model-studio` | Creation / training / evaluation workspace |
| Reports | `/intelligence/reports` | Saved / scheduled Intelligence views |

**Removed from primary Intelligence navigation:**
- **Training** (`/training`) — route preserved for compatibility; exposed inside Model Studio via progressive disclosure (Create · Train · Evaluate · Deploy · Runs)
- Memory — contextual segment inside Learning; `/intelligence/memory` remains routable

**Relocated to Admin only:**
- Platform Health / Observability (TTFT, cache, fallback, deploy smoke, cognitive turns, engine tabs, recent runtime turns)
- `/admin/intelligence` remains engineering console — never linked as peer to Learning content

### 1.2 Contextual sub-navigation (in-page only)

Replace second nav bars with **segmented controls, filters, and drawers**:

```
Learning
  [ Learned Recently ] [ Relationships ] [ Memory ] [ Models ]
  Evidence quality ▾   Confidence ▾   Source ▾   Time range ▾
```

Quality is **filtering / evidence inspection** — not a primary tab.

```
Performance
  [ Business impact ] [ Efficiency ] [ Agents ] [ Cost ] [ Reliability ]     Period ▾
```

```
Predictions
  [ Active ] [ Resolved ] [ By department ▾ ]     Horizon ▾
```

```
Model Studio
  Create · Train · Evaluate · Deploy · Runs
  (Train / Runs link to /training internally)
```

**Delete:** `LearningSurfacesCallout` as parallel top nav on Learning/Training/Models.

### 1.3 Route aliases (unchanged)

Preserve all existing URLs and redirects (`/training`, `/intelligence/predictive`, `/models/built-in`, agent redirects). IA change is **presentation and shell**, not URL breakage.

---

## 2. Page hierarchy and visual identities

Intelligence pages share **one design language** but **not one identical layout**. Do not embed the same full graph on every route.

| Page | Primary job | Layout character |
|------|-------------|------------------|
| **Overview** | Living Intelligence Map | Full interactive graph + lens strip + command surface |
| **Learning** | Learning stream + relationship formation + evidence | Insight stream, relationship canvas, memory panel — graph accents, not hero |
| **Predictions** | Prediction horizon + risk/opportunity topology | Prediction cards + confidence/evidence topology |
| **Performance** | Outcome attribution flows + impact trends | Outcome flow chain + contribution + trends — **not** a KPI dashboard |
| **Models** | Business intelligence catalog + usage topology | Business-first catalog; usage topology as secondary |
| **Model Studio** | Creation / training / evaluation workspace | Intent wizard → pipeline; Train/Runs via `/training` |
| **Reports** | Saved / composed Intelligence views + scheduled outputs | Report builder + saved views |

```
IntelligenceShell (persistent — all hub routes)
├── HubTabs (7 items)
├── FreshnessBar (Live · Updated N sec ago)
├── IntelligenceCommandBar (Ask Gravitre — contextual)
└── PageBody (page-specific — see table above)
```

Every page **inherits** shell primitives; `PageBody` specialization is mandatory and distinct.

---

## 3. Shared Intelligence shell (I1 deliverable)

### 3.1 `IntelligenceShell` — permanent experience frame

I1 establishes the **Intelligence Experience Shell** that all later phases plug into — not merely loading fixes on Overview.

**Always present on hub routes:**
- Single primary `IntelligenceHubTabs` (7 items)
- `IntelligenceFreshnessBar` — snapshot lifecycle state + timestamp
- `IntelligenceCommandBar` — Ask Gravitre command surface (page variant)
- Shared page frame / grid templates
- Contextual filter pattern (segmented controls + dropdowns)
- Collapsed inspector pattern (drawer closed by default)
- Canonical loading / degraded / error states
- Shared page transitions (Framer Motion)
- Route preservation (deep links, back navigation)

**Never present:**
- Duplicate hub rows
- Admin telemetry widgets on customer Learning/Performance
- False zero metrics during load

### 3.2 Visual anchor: Shared Intelligence Core

Persistent conceptual object — full graph on Overview; glyph / strip / topology accents on other pages:

```
                    GRAVITRE INTELLIGENCE
                           ◉
                    shared intelligence
```

Same node/edge/motion vocabulary everywhere; **not** the same full graph canvas on every page.

### 3.3 Cross-page state (`IntelligenceExperienceProvider`)

Single client store for:
- `snapshotState` — UNINITIALIZED | LOADING | READY | REFRESHING | DEGRADED | ERROR
- `activeLens`
- `selectedNodeId`
- `graphViewport` (zoom/pan — session persisted per org)
- `inspectorPinned`
- `snapshotGeneration` (atomic metric commit key)
- `lastKnownSnapshot` (for REFRESHING — preserve visible values)

Deep links: `/intelligence?lens=predicts&focus=prediction:{id}` (existing contract extended)

---

## 4. Graph architecture (renderer-agnostic)

**Do not make Sigma.js (or any renderer) the architecture.** The UI implementation must not become the product architecture.

### 4.1 Layered stack

```
IntelligenceGraph (data + semantics)
        ↓
GraphLayoutEngine (positions, clustering, collision, pins)
        ↓
GraphInteractionController (zoom, pan, drag, focus, selection, keyboard)
        ↓
GraphRenderer (adapter)
        ├── WebGLRenderer (primary — scale, thousands of nodes)
        └── DomSvgRenderer (accessibility, detail overlays, rich node chrome)
```

**Owned outside any renderer:**
- Node/edge semantics and taxonomy
- Layout state, clustering, collision avoidance
- Pin/unpin positions
- Lens filter state
- Selection and focus
- Visualization commands from Ask Gravitre (SSE)
- Animated traces (orchestrated by controller, rendered by adapter)

**Sigma/WebGL is acceptable** as the primary large-scale renderer implementation — but it is an adapter, not the source of truth.

**Keeps open:**
- Alternate renderers
- 2.5D / spatial mode (separate renderer or WebGL depth pass)
- DOM/SVG accessibility representation
- Richer node overlays and contextual chrome
- Future renderer replacement without rewriting product logic

### 4.2 Required interactions (ship blocker)

| Interaction | Owner layer |
|-------------|-------------|
| Wheel / trackpad zoom | InteractionController |
| Zoom in / out / fit / center / reset | InteractionController + toolbar |
| Click-drag pan | InteractionController |
| Drag node / pin / unpin | InteractionController → LayoutEngine |
| Focus selected node | InteractionController |
| Fullscreen | Shell + graph stage |
| Search / filter node types | InteractionController + IntelligenceGraph |
| Expand/collapse cluster | LayoutEngine |
| Hover path highlight / connected emphasis | InteractionController |
| Click edge inspection | InteractionController → Inspector |
| Keyboard traversal | InteractionController |
| Ask Gravitre focus commands | IntelligenceGraph ← SSE visualization | 

### 4.3 Optional advanced mode (opt-in only)

**2D / 2.5D (default) ↔ Spatial** toggle:
- Spatial: subtle Z-depth, parallax, optional orbit — **not** sci-fi camera-first UX
- Default must remain understandable 2D / 2.5D
- Three.js depth pass or alternate spatial renderer — only when user opts in

### 4.4 Interaction quality rule

**No dead interactions.** Every hover/click/drag produces inspectable meaning or is disabled with explanation.

---

## 5. Graph layout strategy (`GraphLayoutEngine`)

**Retire:** hard-coded radial rings (`layoutMapNodes` concentric placement).

**Pipeline:**
1. **Semantic seed** — hierarchical by node class (core center, domains, satellites by lens)
2. **Force simulation** — link/charge/center forces; pin constraints for user-pinned nodes
3. **Semantic clustering** — aggregate when density exceeds threshold; expand on gesture
4. **Collision avoidance** — minimum node spacing; label bounding-box rejection
5. **Label placement** — leader lines; hide below LOD; **never overlap**
6. **Edge routing** — curved; avoid labels; opacity reduction when dense
7. **Cache** — persist positions per org+lens (sessionStorage); warm-start on return
8. **Scale target** — architecture must support **potentially thousands of nodes** via clustering + LOD + WebGL renderer

Layout engine is **renderer-agnostic** — outputs normalized node positions + cluster metadata consumed by any `GraphRenderer`.

---

## 6. Node taxonomy (visual hierarchy)

Map backend `IntelligenceNodeType` to distinct visual classes — **not** uniform rectangles.

| Class | Shape / size | Icon | States |
|-------|----------------|------|--------|
| **CORE** | Large hub, subtle WebGL aura | Nucleo intelligence | idle, trace, pending, flow, resolved |
| **DOMAIN** | Medium department ring | Department glyph | activity-weighted |
| **OBJECTIVE** | Hex / flag | Target | progress |
| **AGENT** | Persona card (compact) | Agent avatar gradient | configured vs running |
| **MODEL** | Capability tile | CPU/brain | ready / learning |
| **SIGNAL** | Small diamond | Pulse | observation |
| **PREDICTION** | Amber accent card | Warning/forecast | confidence band |
| **ACTION** | Trace node | Bolt | completed / pending |
| **CONNECTOR** | System badge | Integration icon | healthy / degraded |
| **OUTCOME** | Check / result node | Trend | measured |
| **EVIDENCE** | Document node | Link | sourced |
| **ENTITY / KNOWLEDGE** | Type cluster | Database | count badge |
| **LEARNING** | Book insight | Sparkle | promoted |

Node renderers live in `GraphRenderer` adapters; semantics live in `IntelligenceGraph`.

---

## 7. Edge taxonomy

Backend `IntelligenceEdgeType` drives stroke semantics:

| Edge | Visual | Motion |
|------|--------|--------|
| KNOWS, READ_FROM | Thin gray | Slow inward pulse on activity |
| PREDICTS, AFFECTS | Amber dashed → solid by confidence | Outbound pulse |
| EXECUTED, ASSIGNED_TO, USED_BY | Brand green trace | Agent→system animation |
| EVIDENCE_FOR, LEARNED_FROM | Solid resolved green | Flow toward claim |
| CONTRADICTS | Low-confidence dashed | No pulse |
| IMPROVED, PRODUCED, CONTRIBUTED_TO | Outcome feedback | Core-bound flow |
| REQUIRES_APPROVAL | Amber hold | Pulse pause |

Animated traces orchestrated by InteractionController; rendered by adapter.

---

## 8. Motion language

Motion = meaning, not decoration.

| Motion | Meaning |
|--------|---------|
| Inward pulse | Data/observation arriving |
| Core pulse | Reasoning active |
| Edge flow (gradient sweep) | Information movement |
| Outbound pulse | Prediction / recommendation |
| Agent→system trace | Execution in flight |
| Amber pulse | Human attention / approval |
| Outcome→core flow | Feedback incorporated |
| Relationship fade-in | New learning |
| Resolve snap | Verified completion |

**Constraints:** `prefers-reduced-motion` honored; no decorative particle noise; GSAP/Aceternity for hero transitions only.

---

## 9. Loading and refresh state design

### 9.1 Core rule: **UNKNOWN ≠ ZERO**

Explicit page states:

| State | Meaning |
|-------|---------|
| `UNINITIALIZED` | Route mounted; no fetch started |
| `LOADING` | Awaiting first canonical snapshot |
| `READY` | Snapshot committed; all headline UI atomic |
| `REFRESHING` | Background refresh; **preserve last known values** |
| `DEGRADED` | Partial snapshot; show values + source warning |
| `ERROR` | Fetch failed; retry available |

### 9.2 UI rules by state

**LOADING**
```
KNOWS
—
Loading intelligence…
```

**READY**
```
KNOWS
32 entities
```

**REFRESHING** — do not blank or reset to zero
```
KNOWS
32 entities
Refreshing…
```

**DEGRADED**
```
KNOWS
32 entities
Some sources unavailable
```

**ERROR**
```
KNOWS
—
Unable to load · Retry
```

**Never render numeric `0` until the canonical snapshot is resolved and zero is a verified value.**

### 9.3 Atomic metric commit

1. Fetch `GET /api/intelligence/page-context` as canonical source for headline metrics
2. Hold UI in LOADING until first complete snapshot
3. Commit lens strip + graph + summary in **one transition** (`snapshotGeneration` key)
4. Background refresh: transition to REFRESHING; keep `lastKnownSnapshot` visible; animate only changed values; show `Updated just now`

### 9.4 Deprecate staggered legacy fetches

Remove from critical path: parallel `outcomes`, `businessSignals`, `businessImpact`, `coreState` for **headline** numbers. Secondary sections may load independently with their own shells — never mixed into lens strip counts.

---

## 10. Lens behavior

Five lenses filter **one canonical graph** (G1/G3 preserved):

| Lens | Strip example (READY) |
|------|----------------------|
| **KNOWS** | `32 entities · 46 relationships` |
| **LEARNS** | `3 new insights` |
| **PREDICTS** | `4 active predictions` |
| **ACTS** | `1 configured · 0 running` |
| **IMPROVES** | `2 measured outcomes` |

Lens click transforms graph emphasis (Overview). Ask Gravitre SSE drives focus (G4). Compact horizontal strip — not competing KPI cards.

---

## 11. Inspector design

| State | Layout |
|-------|--------|
| No selection | Content **full width**; subtle hint |
| Selection | Right drawer (400px); optional pin |
| Close | Full width restored |

Drawer: business title → context facts → evidence → quality notes (human copy) → actions.

---

## 12. Ask Gravitre interaction design

Intelligence **command surface** — not generic chat pasted above pages.

- Suggested questions from snapshot
- Responses drive: lens, node highlight, focus, drawer, Performance filters
- SSE `AssistantVisualization` authoritative (G4)
- Wired in I4 after graph engine + Overview map exist

---

## 13. Learning page redesign (I5)

### Remove
- Second full-width nav
- TTFT / cache / fallback / deploy / recent turns (Admin → Platform Health)

### Structure
```
LEARNING — What Gravitre has learned from your business
[ Learned Recently ] [ Relationships ] [ Memory ] [ Models ]
Evidence quality ▾   Confidence ▾   Source ▾   Time range ▾

Learned Recently → LearningInsightCard[] + "View on map" (G8)
Relationships → RelationshipGraphCanvas
Memory → organizational knowledge panel + link to /intelligence/memory
Models → models improved from evidence
```

Quality via filters — not a fifth primary segment.

**Data:** single `page-context` with `active_lens=learns`.

---

## 14. Predictions page redesign (I6)

- Business prediction cards: what, horizon, confidence, drivers, impact, evidence, action
- Risk/opportunity topology visualization (not duplicate OAuth cards)
- Unscoped predictions: single honest banner
- No raw status strings

---

## 15. Performance page complete redesign (I7)

### Primary question
**“Is Gravitre making the business better?”**

### Outcome attribution flow — **core of I7, not deferred**

Visual causal chain (interactive, required for Performance ship):

```
OBJECTIVE
      ↓
SIGNAL
      ↓
PREDICTION / DECISION
      ↓
AGENT / WORKFLOW
      ↓
ACTION
      ↓
OUTCOME
      ↓
BUSINESS IMPACT
      ↓
LEARNING
```

Click any step → inspector with evidence path. **Do not ship Performance as another KPI dashboard first.**

### Top summary
Evidence-backed values only. Business copy — never `INSUFFICIENT_DATA` / `NOT_CONFIGURED`.

### View modes
Business impact | Efficiency | Agent performance | Cost | Reliability

### Agent contribution
Compact cards per agent with actions, outcomes, hours saved (if estimated), pipeline influenced, success rate.

**Backend:** extend snapshot or add outcome-path read API as part of I7 scope planning.

---

## 16. Models page redesign (I8)

**Default: Business view** — purpose, business status, where used, performance, learning sources, last updated, recommended improvement.

**Technical view toggle:** architecture, datasets, hyperparameters, drift, logs.

Usage topology as secondary visualization — not engineering registry aesthetic.

---

## 17. Model Studio redesign (I8)

Progressive disclosure:

**Primary actions:** Create · Train · Evaluate · Deploy · Runs

**Intent-first entry:** Predict outcome · Classify/score · Detect anomaly · Forecast · Improve agent · Advanced/custom

**Training fold:** Train and Runs expose `/training` internally — not top-level hub tab.

---

## 18. Reports redesign (I9)

Saved intelligence views, scheduled reports, business/agent/prediction/governance templates — consistent visualization components, not legacy admin tables.

---

## 19. Component architecture

```
apps/web/lib/intelligence/graph/
├── intelligence-graph.ts              # IntelligenceGraph — data + semantics
├── graph-layout-engine.ts             # positions, clustering, collision, pins
├── graph-interaction-controller.ts    # zoom, pan, drag, focus, keyboard
├── graph-renderer.ts                  # adapter interface
├── renderers/
│   ├── webgl-renderer.ts              # Sigma or equivalent — implementation only
│   ├── dom-svg-renderer.ts            # a11y + detail overlays
│   └── spatial-renderer.ts            # optional 2.5D — I9
└── types.ts

apps/web/components/intelligence/
├── shell/
│   ├── intelligence-shell.tsx
│   ├── intelligence-freshness-bar.tsx
│   ├── intelligence-command-bar.tsx
│   ├── intelligence-page-template.tsx
│   └── intelligence-experience-provider.tsx
├── graph/
│   ├── intelligence-graph-stage.tsx   # composes stack layers
│   └── intelligence-graph-toolbar.tsx
├── inspector/
│   ├── intelligence-inspector-drawer.tsx
│   └── quality-copy.ts
├── lenses/
│   └── intelligence-lens-strip.tsx
└── pages/
    ├── overview-stage.tsx
    ├── learning-stage.tsx
    ├── predictions-stage.tsx
    ├── performance-stage.tsx
    ├── models-stage.tsx
    ├── model-studio-stage.tsx
    └── reports-stage.tsx
```

**Rule:** No Sigma imports outside `renderers/webgl-renderer.ts`.

---

## 20. Reusable design primitives

| Primitive | Source |
|-----------|--------|
| Page header | `GravitrePageHeader` (Nodus) |
| Metrics | `GravitreMetric` — `uninitialized` / `loading` / `value` / `refreshing` / `degraded` |
| Surfaces | `GravitreSurface` |
| Tabs | `HubTabs` — 7 items, single row |
| Drawer | Untitled UI Sheet |
| Segmented control | Untitled UI Tabs variant |
| Command input | Ask Gravitre composer |
| Empty states | `EmptyState` + CTA |
| Freshness | `IntelligenceFreshnessBar` |

All colors via `--g-*` and `--np-*` tokens.

---

## 21–25. Design stack integration

- **Nodus:** topology metaphor, hub-and-spoke, intelligence surface gradient, KPI spacing
- **Untitled UI:** controls, drawers, dialogs, tables (technical Models view)
- **Framer Motion:** page transitions, drawer, lens switch, metric morph on refresh
- **Three.js/WebGL:** CORE aura (lazy); primary graph via WebGL adapter; spatial opt-in only
- **GSAP/Aceternity:** outcome flow reveal (Performance); selective signal pulses — not landing-page noise

---

## 26. Mobile strategy (I9)

Do not shrink desktop graph to mobile.

Mobile: focused relationship paths, cards, Ask Gravitre, expandable graph explorer — not 40-node canvas.

---

## 27. Accessibility (I10 hardening)

- Keyboard graph traversal via InteractionController
- DOM/SVG list alternative view (same snapshot data)
- ARIA live regions for selection
- Focus trap in drawer
- WCAG AA contrast
- `prefers-reduced-motion`: static layout, no pulses

---

## 28. Performance strategy

| Target | Approach |
|--------|----------|
| 60fps pan/zoom | WebGL renderer adapter |
| Thousands of nodes | Clustering + LOD + lazy load |
| Memo | Stable keys; split graph vs chrome context |
| Layout cache | sessionStorage |
| No rerender on hover | Transform-only updates |

---

## 29. Backend dependencies

| Need | Status | Phase |
|------|--------|-------|
| Canonical snapshot | Shipped G1 | I1 consumer |
| Page-context per lens | Shipped G3 | I3+ |
| Outcome attribution paths | Partial | **I7 required** |
| SSE visualization | Shipped G4 | I4 |
| Revenue attribution config | Product | I7 empty states |

No new intelligence database. Aggregation extensions only.

---

## 30. Implementation phases (approved order)

**Gate 0:** This spec committed + explicit I1 start approval

| Phase | Deliverable |
|-------|-------------|
| **I1 — Intelligence Shell + State Contract** | Permanent shell: single nav (7 tabs), shared page frame, freshness bar, command surface, contextual filter pattern, collapsed inspector pattern, snapshot state machine (UNINITIALIZED→ERROR), UNKNOWN≠ZERO, page transitions, route preservation. **All later pages inherit this.** |
| **I2 — Graph architecture + interactions** | Renderer-agnostic stack: IntelligenceGraph → LayoutEngine → InteractionController → GraphRenderer. All required interactions. WebGL adapter + DOM/SVG overlay. |
| **I3 — Overview living Intelligence Map** | Product experience built on I2 engine — not the engine itself. Lens strip + full map. |
| **I4 — Ask Gravitre ↔ graph + inspector/evidence** | SSE drives focus; drawer normative; evidence paths. |
| **I5 — Learning rebuild** | Learned Recently / Relationships / Memory / Models; quality filters; admin telemetry removed. |
| **I6 — Predictions rebuild** | Business cards + risk/opportunity topology. |
| **I7 — Performance + outcome attribution** | Impact summary + **outcome flow chain** + view modes + agent contribution. Not KPI dashboard. |
| **I8 — Models + Model Studio** | Business catalog; intent wizard; Training folded into Studio. |
| **I9 — Reports + mobile + spatial opt-in + polish** | Saved views; mobile paths; optional 2.5D. |
| **I10 — Production eval / UX regression / hardening** | Prod batteries, a11y audit, perf profiling, screenshot evidence. |
| **I11 — Contract reinforcements** | CI customer-surface guards; ERROR lens never false-zero; hub 7-tab + Training-fold tests; admin-import ban on customer Intelligence. |
| **I12 — Live eval closure** | Re-run G1/G4/G8 batteries against current SHA; axe/contrast on Overview + Reports; screenshot List vs canvas. |
| **I13 — Graph density / LOD** | Label collision, cluster expand UX, transform-only pan at higher node counts. |

**Gates:**
- Do not start I2 until I1 shell verified
- Do not start I3 until I2 interaction architecture verified
- Graph engine ≠ Overview product experience — build engine first, then map

---

## 31. Regression risks

| Risk | Mitigation |
|------|------------|
| Renderer lock-in | Adapter boundary; no Sigma outside renderer file |
| G1 active-agent trust | Deterministic chat path; regression battery |
| False zero metrics | State machine + lastKnownSnapshot |
| Performance ships without outcome flow | I7 acceptance requires flow component |
| Same graph on every page | Page visual identity table (§2) enforced in review |
| Training nav confusion | Remove from HubTabs; redirect UX in Model Studio |
| Admin telemetry leak | Route guard; no admin imports on customer pages |
| False-zero after READY | I11 ERROR/LOADING lens placeholders; CI leak guard for raw quality flags |
| Hub IA drift | I11 seven-tab + Training-fold unit/e2e contract |
| Live eval skipped | I12 required before calling the rebuild “closed” |

---

## 32. Acceptance criteria

### Product
- [ ] Intelligence feels like one system with distinct page jobs — not seven dashboards
- [ ] Overview graph: zoom, pan, drag, focus, search, no overlapping labels
- [ ] Lens metrics never show false `0` during load
- [ ] REFRESHING preserves last known values
- [ ] Learning: one hub nav; Learned Recently segment; quality as filters
- [ ] Performance: outcome attribution flow ships with I7
- [ ] Training accessible via Model Studio, not primary nav
- [ ] Zero raw `INSUFFICIENT_DATA` / `NOT_CONFIGURED` in customer UI

### Technical
- [ ] Graph stack is renderer-agnostic (adapter test: swap mock renderer)
- [ ] All hub pages use `IntelligenceShell`
- [ ] Headline metrics from single snapshot commit
- [ ] G1/G4/G8 prod batteries PASS after each phase (**I12** re-run on post-I10 SHA)

### Evidence (I10 + per phase)
- [ ] Before/after screenshots in delivery report
- [ ] Prod trace or CI Playwright for critical paths
- [ ] I11 customer-surface CI guard green

---

## 33. Post-I10 reinforcement program (Revision 3)

I1–I10 shipped the experience. These phases **harden the contract** so the rebuild cannot regress into dashboards, false zeros, or admin leaks.

| Phase | Why |
|-------|-----|
| **I11** | Shift-left: static guards + lens/hub unit tests catch class-level leaks before prod batteries |
| **I12** | Evidence-linked PASS: live G1/G4/G8 + a11y scan + screenshots on the deployed SHA |
| **I13** | Graph remains thinkable at density: collision, LOD, 60fps pan without hover rerenders |

I11 does not invent scheduled-report APIs, prices, or Enable toggles.

---

## Appendix A — Copy mapping (machine → human)

| Internal | Customer copy |
|----------|---------------|
| `INSUFFICIENT_DATA` | Not enough verified data yet |
| `NOT_CONFIGURED` | Not set up yet — [Configure →] |
| `UNSCOPED_PREDICTION` | This signal needs a connected source |
| `NO_BUSINESS_LEARNING_YET` | No validated business learning in this period |

Centralize in `apps/web/lib/intelligence/quality-copy.ts`.

---

## Appendix B — Approved product decisions (2026-09-13)

| Decision | Status |
|----------|--------|
| Single-nav IA (7 tabs) | **Approved** |
| Training folded under Model Studio | **Approved** |
| Learning contextual segments (Learned Recently · Relationships · Memory · Models) | **Approved** |
| Quality as filters, not primary tab | **Approved** |
| UNKNOWN ≠ ZERO + explicit state machine | **Approved** |
| I1 before I2; strengthened I1 shell | **Approved** |
| Renderer-agnostic graph architecture | **Approved** |
| Spatial/3D opt-in only | **Approved** |
| Performance outcome flow in I7 (not deferred) | **Approved** |
| Page-level visual identities (same language, different jobs) | **Approved** |
| Phases I1–I10 as defined in §30 | **Approved** |
| Post-I10 reinforcements I11–I13 | **Added Revision 3 (2026-09-16)** |

**Next gate:** **I12** live eval closure (G1/G4/G8 + a11y) after I11 is on production.

---

## Change log

### Revision 3 — 2026-09-16 (post-I10 reinforcements)

Added §33 and phases **I11–I13**: customer-surface CI guards, live eval closure, graph density/LOD. Does not reopen I1–I10 product decisions.

### Revision 2 — 2026-09-13 (product sign-off incorporated)

| Area | Revision 1 | Revision 2 |
|------|------------|------------|
| **Status** | DRAFT | APPROVED (pending I1 start gate) |
| **Primary nav** | 8 tabs incl. Training | **7 tabs**; Training folded into Model Studio |
| **Learning segments** | Recent · Relationships · Memory · Models | **Learned Recently** · Relationships · Memory · Models |
| **Learning quality** | Fifth content section | **Filters only** (Evidence quality, Confidence, Source, Time range) |
| **Loading states** | LOADING / READY / REFRESHING / DEGRADED / ERROR | Added **UNINITIALIZED**; explicit UI copy per state; REFRESHING preserves last known values |
| **I1 scope** | Shell + loading contract | **Intelligence Experience Shell** — permanent frame all pages inherit |
| **Graph architecture** | Sigma recommended as default | **Renderer-agnostic stack** — IntelligenceGraph → LayoutEngine → InteractionController → GraphRenderer; Sigma/WebGL as adapter only |
| **Overview vs engine** | Combined in I2 | **Split:** I2 = architecture; I3 = living map product experience |
| **Ask Gravitre + inspector** | I3 | **I4** (after map exists) |
| **Performance outcome flow** | I6 with optional Phase 2 defer | **I7 core requirement** — not KPI dashboard first |
| **Training** | Optional collapse later | **Removed from hub**; `/training` preserved; exposed in Model Studio |
| **Page layouts** | Implied shared graph | **Explicit page visual identities** — same language, different jobs; no full graph on every route |
| **Phases** | I1–I9 | **I1–I10** — added I10 prod eval / a11y / perf hardening; reordered I5–I9 |
| **Model Studio** | Basic wizard | Create · Train · Evaluate · Deploy · Runs |

### Revision 1 — 2026-09-13

Initial redesign specification (32 sections). Supersedes incremental graph polish. Builds on G1–G8 canonical state.

---

*Canonical design/architecture document for the Intelligence Experience Rebuild. Commit to repo; do not treat as ephemeral chat instruction.*

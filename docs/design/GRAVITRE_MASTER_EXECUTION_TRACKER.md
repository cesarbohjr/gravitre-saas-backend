# Gravitre Master Execution Tracker

**Authority:** Cesar master directive 2026-09-20 — UX Reset 2.0 + UX/UI 3.0 Plus + CES 2.0  
**Statuses:** `NOT STARTED` · `IN PROGRESS` · `IMPLEMENTED — NOT PROVEN` · `VERIFIED` · `BLOCKED`  
**Also used for browser rows:** `PASS` · `FAIL` · `BLOCKED` · `NOT PROVEN`

---

## Document conflicts

| Conflict | Resolution |
|----------|------------|
| Activity-first vs Intelligence-first | Intelligence first (master directive) |
| Cesar I1+I2 design gate | **CLOSED — approved** — do not reopen |

---

## Phase 2 — Intelligence I1 + I2

### Deployment / API (accepted baseline)

| REQUIREMENT | STATUS | EVIDENCE |
|-------------|--------|----------|
| Cesar design approval | VERIFIED | Approval directive |
| KG SELECT + field sample | VERIFIED (API) | tip `61f75c4f` · `docs/delivery/i1-i2-live-recount.json` |
| Prod OverviewLivingMap I1+I2 | IMPLEMENTED — NOT PROVEN (UI) | commits `22c59fae`…`61f75c4f` · Vercel READY |
| G8 live API | VERIFIED | `docs/delivery/g8-intelligence-hub-live.json` PASS |

### Authenticated browser matrix (`https://gravitre.app/intelligence`)

| Check | Result | Notes |
|-------|--------|-------|
| Session available | **BLOCKED** | 2026-09-20 · agent browser navigated to `/intelligence` → redirected to `https://gravitre.app/login` (Welcome back / SSO+password). No authorized cookie/session in agent browser. |
| Initial field | NOT PROVEN | Requires session |
| KNOWS / LEARNS / PREDICTS / ACTS / IMPROVES | NOT PROVEN | Requires session |
| Node / relationship / I2 / Ask / list-spatial / search | NOT PROVEN | Requires session |
| Loading / empty / sparse / error / mobile / reduced | NOT PROVEN | Requires session |
| Old IntelligenceGraphStage not default | NOT PROVEN | Code path uses OverviewLivingMap; browser unconfirmed |
| KG counts visible in UI (org-specific) | NOT PROVEN | API recount for isolated org only — not claimed for every org |

**Intelligence production VERIFIED:** no — browser gate open.

**Limitation (exact):** Cursor IDE browser tabs hold only public login; cannot complete Gravitre SSO/password without exposing credentials. API verification remains separate and PASS for the isolated org recount.

---

## Phase 3 — Activity A1 + A2

| REQUIREMENT | STATUS | FILES | TEST |
|-------------|--------|-------|------|
| A1 TRACE rail + story on `/activity` | IMPLEMENTED — NOT PROVEN | `components/activity/activity-trace-panel.tsx` · wired in `app/activity/page.tsx` | vitest `activity-trace-panel.test.ts` |
| A2 timeline on demand | IMPLEMENTED — NOT PROVEN | same panel · Story/Timeline toggle | unit |
| Reuse P-1 grammar | VERIFIED (reuse) | EvidenceChip + grammarToneForStepStatus | — |
| Prod browser Activity | NOT PROVEN | awaits auth session | — |

---

## Authenticated browser verification

**AUTHENTICATED BROWSER VERIFICATION — BLOCKED: NO AUTHORIZED SESSION.**

Recorded once. Does not block implementation of independent phases. Do not mark browser matrices PASS. Resume when a session exists. Do not request credentials.

Applies to: Intelligence, Activity, Navigation, and later surfaces until a session is available.

---

## Phase 4 — Navigation B (expandable labeled rail)

Commit `7c9ac89e` is on `main`.

| REQUIREMENT | STATUS | EVIDENCE |
|-------------|--------|----------|
| Click expand (not hover-only) | IMPLEMENTED — NOT AUTHENTICATED-BROWSER-PROVEN | `app-shell.tsx` hamburger + persisted `gravitre-nav-expanded` |
| Pin labels | IMPLEMENTED — NOT AUTHENTICATED-BROWSER-PROVEN | Sidebar `nav-pin-labels` → same persisted toggle |
| Keyboard arrows | IMPLEMENTED — NOT AUTHENTICATED-BROWSER-PROVEN | `cycleNavFocus` + sidebar keydown · vitest 3/3 `nav-rail-focus.test.ts` |
| Mobile drawer | IMPLEMENTED — NOT AUTHENTICATED-BROWSER-PROVEN | Existing overlay; hamburger opens drawer <768 |
| Destinations / org / admin-lite / notifications / AI / palette | PRESERVED | No second nav architecture; top bar unchanged |
| Authenticated browser | BLOCKED | No authorized session. Not production VERIFIED. |

---

## Phase 5 — Requirements matrix

Authenticated browser for every row: **BLOCKED: NO AUTHORIZED SESSION**. That does not block the implementation status below.

| SURFACE | APPROVED REQUIREMENT | CURRENT IMPLEMENTATION | CATEGORY | CHANGE MADE | TEST EVIDENCE | BROWSER EVIDENCE | STATUS | NEXT ACTION |
|---------|----------------------|------------------------|----------|-------------|---------------|------------------|--------|-------------|
| Agents | Operate team; open profile/handoff; animate delegate edge only on a real handoff; remove giant avatar orbs | Team view is default (compact identity, no hub). Graph edges from parent, swarm, connectors. Inspector opens on select. | A implemented. C: no new fleet spatial model. | Graph sweep runs only when `edge.active` (in-flight swarm). Idle edges stay still. | `phase-3-product-ia.test.ts` asserts `sweep={active}` and no hub on team | NOT RUN — login wall | IMPLEMENTED — NOT AUTHENTICATED-BROWSER-PROVEN | None until a session exists |
| Relationships | Edge + provenance inspect; trace on select; canvas idle | `RelationshipsWorkspace` graph/table + inspector provenance copy and `TracePath`. Mounted from Intelligence learning and admin intelligence. | A already present. C: do not replace the canvas with another spatial model. | None. Working canvas preserved. | Existing IA test: graph mode, selection, no metrics dashboard | NOT RUN — login wall | IMPLEMENTED — NOT AUTHENTICATED-BROWSER-PROVEN | None |
| Workflows | Author/verify; configure/run; execution overlay only on a real run; remove decorative chrome | Builder canvas, node inspect, `traceOverlay`. Connection particles previously looped on idle edges. | A | Glow and flow particles render only when the source node is running, success, or evaluating (or a chosen decision path). | `phase-3-product-ia.test.ts` asserts `isActive && !isDimmedPath` | NOT RUN — login wall | IMPLEMENTED — NOT AUTHENTICATED-BROWSER-PROVEN | None |
| Connectors | Discover then manage; connect/repair; animate only real OAuth; no logo-wall default | Default `viewMode` is the compact list. Topology is opt-in. | A already present. | None. | Existing IA test: default `"grid"`, `variant="list"`, discovery strip | NOT RUN — login wall | IMPLEMENTED — NOT AUTHENTICATED-BROWSER-PROVEN | None |
| Sources | Ingest/verify; remove card-first grids where a table wins; pulse only on a real syncing job | Table of existing source fields. `rag_sources.status` is set to `syncing` by `source_sync_service` during a sync. | A | Category list is a table. Status cell pulses only when `status === "syncing"` (`motion-safe`). Last sync and generic connected/error do not pulse. Selected row still opens the existing tile. | `phase-3-product-ia.test.ts` asserts `<table`, no `xl:grid-cols-4`, and `data-source-ingest="syncing"` | NOT RUN — login wall | IMPLEMENTED — NOT AUTHENTICATED-BROWSER-PROVEN | None |
| Approvals | One primary Approve; continue the same run; remove multi-CTA clutter | Queue selects; inspector Approve is primary; row says “Select to decide”; same-path chip when `runId` exists. | A | Desktop inspector keeps Approve. Mobile uses only the sticky bar (`lg:flex` footer hidden below `lg`) so Approve is not shown twice. | Existing IA test plus `hidden items-center gap-3 lg:flex` | NOT RUN — login wall | IMPLEMENTED — NOT AUTHENTICATED-BROWSER-PROVEN | None |
| Marketplace | Discover and install real catalog objects. Visual density is an unselected replacement layout (`GRAVITRE_3.0_PLUS_CESAR_APPROVAL_PACKAGE.md`: “Heavy redesign; own slice”). | Catalog remains the existing featured + card grid (`data-review-surface="marketplace-discovery"`). Prices stay on asset records. | C — open | None. A table or new discovery object would be a new concept. | Not rewritten | NOT RUN — login wall | PRESERVED — open layout decision | Do not redesign until a density layout is selected |
| Models | Honest readiness; no fake TRAINED; no decorative motion | Catalog/studio are list + inspector. No `TRAINED` string on `/models` or the built-in brain. | A already present. | None. | Existing IA test: list + inspector, not card grids | NOT RUN — login wall | IMPLEMENTED — NOT AUTHENTICATED-BROWSER-PROVEN | None |
| Settings | Shared shell and Navigation B. No separate settings spatial model in the approved surface table. | Settings routes already use `AppShell`. Org switch stays inspector-on-selection. | B already present. | None. | Existing IA test: settings orgs inspect, no card chrome | NOT RUN — login wall | IMPLEMENTED — NOT AUTHENTICATED-BROWSER-PROVEN | None |
| AI Workspace | Morph the existing workspace; one `useChat`; voice uses the existing visualizer, not the marketing orb | `useChat({` is called in `ai-workspace.tsx` only. Voice comments keep the orb as presentation, not a second runtime. | A already present. C: no second runtime and no marketing-orb import. | None. | `selected-entity-context.test.ts` reads that `useChat({` transport body | NOT RUN — login wall | IMPLEMENTED — NOT AUTHENTICATED-BROWSER-PROVEN | None |

### Category C

1. **Marketplace discovery density — still open.** The approval package marks this as a heavy redesign and its own slice. Existing rules also say marketplace objects are premium discovery, not an operations table. No layout was selected, so the catalog is unchanged.
2. **Sources ingest pulse — closed.** `source_sync_service` writes `rag_sources.status = "syncing"` for a real sync. The table pulses only on that status. Last-sync text does not drive motion.
3. **Agents and Relationships spatial models — closed by preservation.** Team, list, graph, and the relationships canvas stay. No additional model was added.

Do not reopen Intelligence I1/I2, Activity A1/A2, or Navigation B.

Phase 5 commit, CI, and deployment are recorded after the commit lands. Authenticated browser remains BLOCKED: NO AUTHORIZED SESSION.

---

## Phase 6 — CES 2.0

| REQUIREMENT | STATUS |
|-------------|--------|
| KF-A harness (locked concept) | IMPLEMENTED — NOT PROVEN (harness) |
| Production Pilot 3 promote | BLOCKED — separate promote gate |
| Pilot 1 / 2 reopen | NOT STARTED (locked — do not reopen) |


# 25 — Phase 8 Area 15 acceptance record

**Branch:** `feat/gravitre-3.0-plus-frontend` (not merged, not deployed).
**Rendered frontend SHA:** `7dec9c47fe2dbad463aea89a923b71738416909f` (build `E2FBQmpdG6-RTMiGpvZow`).

| Gate | Status |
|------|--------|
| VISUAL_ACCEPTANCE (fixture test tenant) | ACCEPTED with the exceptions listed below |
| OWNER_LIVE_ACCEPTANCE (Cesar's account) | NOT RUN |
| Billing E2E | NOT GREEN (classified below) |

## Evidence classes

- **VISUAL_ACCEPTANCE** — production build (`next build` + `next start`) of the exact candidate SHA,
  served at `http://127.0.0.1:3010`, signed in as the existing E2E billing fixture tenant
  (`activeTrial` in `e2e/.fixtures/billing-users.json`, org "Billing E2E active …"). Auth and data come
  from production Supabase and `api.gravitre.app` for that test tenant only. Captures are fixture-tenant
  data, not customer or owner data.
- **OWNER_LIVE_ACCEPTANCE** — same frontend against Cesar's owner account. Not run. It must still prove
  owner authentication, real workspace data, AI workspace, inspector, conversation identity, responsive
  behaviour and no entitlement regressions.

No production auth, entitlement, or auth-architecture change was made for this capture.

## Build identity

`docs/delivery/ui-3-0-plus-phase-8/build-identity.txt` records SHA, branch, clean web tree, and build
window. `manifest.json` records the BUILD_ID the browser was served.

Three-screen proof (`proof/agents.png`, `proof/marketplace.png`, `proof/workflows.png`), checked in the
browser on each screen: page HTML contains the BUILD_ID, `/_next/static/<BUILD_ID>/_buildManifest.js`
returns 200, none of the retired strings render ("One Intelligence Core", "TEAM default",
"list and graph remain", "Counts for the current filters", "not a second dashboard",
"authorized commerce", "Edges: parent", "Last Run", "Success Rate", "1 App To Connect"), and zero
uppercase letter-spaced micro-labels remain in `main`, `aside`, or dialogs.

## Screenshot set

`docs/delivery/ui-3-0-plus-phase-8/` — 95 route captures plus 3 proof captures.

Sets: `desktop-light` (1440×900), `tablet-light` (834×1112), `mobile-light` (390×844),
`desktop-dark`, `mobile-dark`.

Routes per set: Dashboard, AI workspace, Agents, Agents inspector, Agent detail, Personality,
Workflows, Workflow Builder, Intelligence, Model Studio, Connectors, Sources, Marketplace, Goals,
Assignments, Approvals, Schedules, Administration (Platform intelligence), Settings.

A production "before" set was not captured in this pass.

## Rendered-review fixes

Found by reviewing the rendered captures, fixed at the level where they live, recaptured on the next SHA.

| Commit | Level | Fix |
|--------|-------|-----|
| `9da6a3ff` | Shared primitive | `ToggleGroupItem` used `flex-1 min-w-0` inside a `w-fit` group, clipping the longest label ("Conversatio"). Now `flex-auto`. |
| `9da6a3ff` | Shared shell | AI launcher sat on top of the sidebar rail's last item. From `md` it now offsets past `--np-sidebar-rail` / `--np-sidebar`. |
| `9da6a3ff` | Shared pattern | Seven collapsed metric disclosures (Workflows, Marketplace, Connectors, Intelligence performance ×2, Run detail ×2) had no open/closed cue. New `.g-disclosure` chevron. |
| `9da6a3ff` | Copy | Design notes shown to customers: "Catalog prices are authorized commerce…", "Do not invent a waterfall", "they do not invent rows", "Do not invent nodes", `org_entity_relationships` table name, "displayable field nodes". Replaced with plain copy. |
| `9da6a3ff` | Route | Workflows table headers "Last Run" / "Success Rate" → sentence case. Marketplace rows no longer title-case the connector summary. Agents "Edges" legend only in Graph view. Mobile Agents search gets its own row. |
| `7dec9c47` | Route | Tablet Workflow Builder header collapsed the workflow name to zero width. Toolbar labels are `sr-only` below `lg` (names kept for assistive tech; previously `hidden`, which removed them). |
| `7dec9c47` | Shared shell | On the Builder, the launcher is icon-only below `xl` so it clears the canvas toolbar. |
| `7dec9c47` | Shared shell | Scrollable pages pad `main` (`pb-32 md:pb-24`) so the fixed launcher never covers the last content at scroll end (seen on Model Studio). |
| `7dec9c47` | Route | Agent detail hero showed status twice (avatar dot plus chip). Avatar dot disabled; the chip carries status. |

Regression coverage: `customer-copy-guard` (new banned phrases), `micro-label-guard` (sentence-case
table headers; bordered disclosures must use `g-disclosure`), `toggle-group-sizing`,
`ai-helper-mobile-offset` (rail offset, builder compact label, main padding), `agent-hero-status`,
`builder-header-labels`.

Earlier convergence on this branch: `6b76c40d`, `ae8af8e3`, `6073e810`, `643e6454`, `3dd67026`,
`2181415a`, `b97cec31`, `0dff6efa`, `1e254277`.

## Remaining visual exceptions

1. **AI workspace empty conversation** — fullscreen and mobile show a blank conversation area before the
   first message. The body is rendered by protected `app/ai/_components/ai-workspace.tsx`. Dependency
   for the core agent; not edited here.
2. **Mobile launcher over scrolling content** — the floating button overlays list rows while scrolling
   (standard FAB behaviour). At scroll end it no longer covers content.
3. **Fixture-tenant data** — trial banner, "E2E Org" label in the org switcher (seeded by the capture
   script's localStorage), 0-count empty states and backend 401/403/404 console errors belong to the test
   tenant, not to the frontend.
4. **Voice library names** (e.g. "Adam - Dominant, Firm") are provider data, shown as returned.

## E2E / CI classification

Exact-SHA runs: [36217779736](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36217779736)
(`9da6a3ff`), [36219084281](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36219084281)
(`7dec9c47`). Push-gated jobs — Backend (pytest), Web (lint + typecheck + build), Integration Smoke
Test, Dependency audit, Shared runtime text/voice gate — success on both. Billing E2E cancelled at its
20-minute limit on both (`7dec9c47`: reached test 78 of 218; 62 passed, 8 failed after retry).

| Test | Class | Evidence and disposition |
|------|-------|--------------------------|
| `canonical-ai-workspace.spec.ts:11` | A (fixed) | First open resolves to `floating` per G-STRUCT A3. Spec aligned in `7ecc7336`. |
| `canonical-ai-workspace.spec.ts:247` | B (protected runtime) | Dev-only duplicate submit under React Strict Mode; `AiWorkspace` composer-intent effect is not idempotent. Proven with `reactStrictMode: false` (one POST). Dependency below. |
| `canonical-ai-workspace.spec.ts:327` | INCONCLUSIVE (possible D) | Passed first attempt on `7ecc7336`, `c18af0b5`, `9da6a3ff`; failed both attempts on `7dec9c47` (runtime never mounted within 90 s). Same SHA locally: 4/4 pass. Not proven a flake; recheck on the next run. |
| `execution-result-navigation.spec.ts:4` | C (fixed) | `main` renamed the label to "Open in Apollo". Spec aligned. |
| `execution-result-navigation.spec.ts:40` | B / C (protected surface) | `ChatExecutionPanel` no longer renders hosted-file chips. No branch diff to the panel. |
| `billing-overview-failure-no-node-default.spec.ts:17` | C (fixed) | Post-login redirect race; fixed in `1e0a4496`. |
| `app-navigation-crawler.spec.ts:30` | C (partly fixed) / D | 4/17 → 12/17 → 15/17. Remaining: backend 401/400 console errors for the CI tenant on `/agents` and `/connectors`. No frontend change involved; not proven on `main` because the job never runs there. |
| `creative-pilot3-knowledge-fabric-widths.spec.ts` (6–9) | C (existing failure) | Component only mounted in a dev prototype. Fixing means adding marketing claims; left for an authorized owner. |
| Billing E2E timeout | C (CI infrastructure) | 218 tests, 1 worker, `timeout-minutes: 20`. `ci.yml` marks the job "Manual/signal only — do not run on main push". Not changed here. |

## Protected core dependencies

1. `app/ai/_components/ai-workspace.tsx` — make the composer-intent effect idempotent per nonce.
2. `app/ai/_components/ai-workspace.tsx` — empty-conversation state for the fullscreen / mobile body.
3. `components/gravitre/assistant/chat-execution-panel.tsx` — confirm or restore hosted-file chips.

## Remaining to accept Phase 8

1. OWNER_LIVE_ACCEPTANCE walk on Cesar's account.
2. Billing E2E green or its exceptions accepted by their owners.
3. Cesar's merge and deploy approval.

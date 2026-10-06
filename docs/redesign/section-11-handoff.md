# Gravitre redesign — Section 11 delivery report

Branch: `v0/assignment-deliverable-report`. Nothing in this report has been deployed to gravitre.app. Section 11 forbids deploying from the master prompt, so that needs a separate explicit instruction.

Each surface is reported against separate evidence types, as Section 11 requires:
**Source** (code changed), **Visual** (rendered screenshot at 907×797 dark, using the `/e2e/shots/*` test pages and fixture data), **Tests** (vitest), **Live API**, **Owner tenant** and **Deploy**.
A screenshot is not evidence of persistence or backend authorization. Live API, owner-tenant and deploy evidence were **not collected** for any surface in this pass.

---

## 1. Recovery diagnosis and preserved functionality

**Diagnosis.** The product's main problems were in the presentation layer, not in the data layer:

- **Too many competing primary actions.** Headers on Agents, Workflows, Connectors and Connector detail had 3–5 buttons with the same weight.
- **Repeated content.** The Dashboard had a second, page-level composer next to the global Ask bar. The multi-agent inspector showed the recommendation three times. Connector and Source detail repeated fields in both the status grid and the overview.
- **Leaked internal values.** Raw agent IDs (`agt_…`), connector slugs (`hubspot`) and lowercase status enums were shown instead of names.
- **Light-mode-only fills.** Tinted cards and evidence chips used fixed pale backgrounds that turned into glaring blocks in dark mode.
- **Layout bugs at tablet width.** Labels only appeared at 1024px and up, filters stacked into tall columns, and headers were double-indented because both the header and its wrapper added padding.
- **Risky interactions.** One click on a Builder connection deleted it.

**Preserved.** No API contract, route, permission check, data fetch or persistence path was changed. Every control that was removed from a header is still reachable:

| Removed from header | Where it lives now |
| --- | --- |
| Agents "Multi-agent run" | Multi-agent tab on the same page |
| Workflows "Create from Goal" / "Build with Meson" | "Start from" menu next to New workflow |
| Workflows Filter | Search toolbar |
| Connector / Source "Back" | Breadcrumb (`Connectors` / `Sources`) |
| Dashboard page composer | Global Ask Gravitre bar and contextual question chips |
| Duplicate overview fields | Status grid (single source) |

Existing test hooks were kept, including `AskGravitreSummonButton` and the swarm panel's "Close detail" button, which the drawer can opt out of.

## 2. Route / control disposition matrix

Disposition values: **Redesigned** (changed and visually reviewed), **Reviewed** (rendered and met the spec, no change needed), **Not reviewed** (no evidence collected yet).

| Family | Route | Disposition | Source | Visual | Tests | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| Assignments | `/assignments`, detail, deliverable | Redesigned (earlier batches) | yes | yes | yes | Phone breakpoint not re-captured this pass |
| Dashboard | `/home` | Redesigned | yes | yes | yes (`phase-5-contextual-ask`) | — |
| Agents | `/agents` | Redesigned | yes | yes | type-check | — |
| Plays | `/plays` | Reviewed | — | yes | — | — |
| Workflows | `/workflows` | Redesigned | yes | yes | type-check | — |
| Builder | `/workflows/[id]/builder` | Redesigned | yes | yes | browser: select → Delete removes edge | Edge selection uses Delete/Backspace and the X marker; no undo |
| Runs | `/runs/[id]` | Redesigned | yes | yes | type-check | — |
| Schedules | `/schedules` | Reviewed | — | yes | — | — |
| Intelligence | Field, Learning, Memory, Performance, Predictions, Reports | Redesigned (tints, header alignment) | yes | yes | type-check | Overview test page only renders the tab strip |
| Relationships | `/intelligence/relationships` | Redesigned (toolbar wraps) | yes | yes | type-check | — |
| Multi-agent | `/multi-agent-run` | Redesigned | yes | yes (list, completed, failed) | 19 swarm tests | — |
| Connectors | `/connectors` | Redesigned | yes | yes | type-check | — |
| Connector detail | `/connectors/[id]` | Redesigned | yes | yes | 9 tests | — |
| Sources | `/sources`, `/sources/[id]` | Redesigned (detail) | yes | yes | type-check | Knowledge has no standalone route; it lives inside Sources and Agents |
| Settings / Billing / Audit | `/settings/*`, `/audit` | Redesigned (billing month), Reviewed | yes | yes | type-check | — |
| Activity | `/activity` | Reviewed | — | yes | — | — |
| Approvals | `/approvals` | Redesigned (chip noise, dark tints) | yes | yes | type-check | — |
| Notifications | `/notifications` | Redesigned (plain-language stats) | yes | yes | 10 tests | Native `<select>` for type filter not restyled |
| Lite | `/lite/*` | **Not reviewed** | — | — | existing `lite-operating-states` tests | `/lite` only redirects. Needs a test page for the real Lite home |
| Meson | Builder Meson tab | Reviewed; empty-state copy corrected | yes | Initial panel at 907×797 dark | Browser: Open step → Data Validator inspector | Updated copy could not be recaptured: preview returned 502 SANDBOX_NOT_LISTENING. AI suggestions, saved-workflow edits and apply remain unverified. |
| Onboarding | `/welcome` (`/onboarding` redirects) | **Not reviewed** | — | — | — | Needs a test page for `/welcome` |
| Desktop | desktop shell routes | **Not reviewed** | — | — | — | — |
| Public | `/`, `/pricing`, `/login`, marketing | **Not reviewed** | — | — | — | Dev server dropped during capture |
| Goals, Marketplace, Models, Training | — | **Not reviewed** this pass | — | — | existing journey tests | — |

This matrix covers the families the master prompt names. Section 11 asks for it to be regenerated from the repository, and that full per-route regeneration has **not** been done. Routes outside these families are unaccounted for.

**Control records for changed controls:**

| Control | Trigger | Result | Pending / error | Keyboard | Return path |
| --- | --- | --- | --- | --- | --- |
| Builder connection | Click line | Selects (highlighted, X marker shown) | — | Delete / Backspace removes; Esc or canvas click clears | Click canvas or a node |
| Builder connection X | Click marker on selected line | Removes connection | — | Focusable button | — |
| Workflows "Start from" | Click | Menu: Goal, Meson | — | Menu keyboard via Radix | Esc closes |
| Connectors filters | Toolbar | Filter list in place | — | Native focus order | — |

## 3. Assignments journey

Delivered in earlier batches: list → creation → detail → readable deliverable → review → recovery. Dark tablet evidence was re-checked during the section 5 gate. Phone and sparse/long-content states were **not** re-captured in this pass.

## 4. Canonical system decisions applied

- **One primary action per header.** Secondary actions go in a menu or toolbar.
- **Breadcrumbs replace "Back" buttons.**
- **Tints are mixed into the theme surface** (`color-mix` with the theme's own background), never fixed light colors, so they work in both light and dark mode.
- **Definition grids for evidence.** Two columns, with empty values dimmed.
- **Human labels only.** Vendor names, agent names, and capitalized statuses instead of slugs, IDs and enums.
- **Labels from 768px**, not 1024px, wherever they fit.

## 5. Use of existing components and contracts

All changes reuse existing components (`GravitrePageHeader`, `ExtrovertSummary`, `EvidenceChip`, `GravitreMetric`, `SwarmRunDetailPanel`, the existing Builder canvas) and existing SWR keys. The only new data call is the agent-name lookup in the swarm panel. It reuses the agents list the start dialog already loads and falls back to the ID when names are unavailable.

## 6. Remaining routes, decisions and unverified behavior

**Remaining routes:**
- Lite home
- `/welcome` onboarding
- Meson standalone
- Desktop shell
- Public / marketing pages
- Goals, Marketplace, Models, Training
- Full repository route regeneration

**Product decisions for the owner:**
- Whether Builder connection delete needs undo.
- Whether the Notifications type filter should become a segmented control.
- Whether Knowledge deserves a standalone route.

**Unverified behavior:**
- Live API and owner-tenant behavior for every surface.
- Phone breakpoints for everything except Assignments.
- Light mode for surfaces changed in this pass.
- Hover, focus, loading and permission-denied states, except where existing tests cover them.

## 7. Integration handoff

**Changed areas this pass:**
- `components/home/*`, `app/agents/page.tsx`
- `app/workflows/page.tsx`, `app/workflows/[id]/builder/page.tsx`, `app/runs/[id]/page.tsx`
- `components/gravitre/extrovert-summary.tsx`, the four Intelligence pages, `components/intelligence/relationships/*`
- `components/agent-swarm/swarm-run-detail-panel.tsx`, `lib/swarm-result-format.ts`, `app/multi-agent-run/page.tsx`
- `app/connectors/page.tsx`, `app/connectors/[id]/page.tsx`, `components/connectors/connector-linkage.tsx`
- `app/settings/billing/page.tsx`
- `app/sources/[id]/page.tsx`, `app/approvals/page.tsx`, `components/marketing/creative/primitives/evidence-chip.tsx`
- `app/notifications/page.tsx`

**Test-only additions:**
- `app/e2e/shots/multi-agent-run`, `app/e2e/shots/notifications`
- Swarm fixtures in `lib/e2e-shot-fixtures.ts`

**Tests updated:**
- `phase-5-contextual-ask` (page composer removed)
- `notification-inbox` (stat label)

**Assumptions:**
- The 907×797 dark preview is the primary review viewport.
- Fixture data is representative of real data.

**Risks:**
- `EvidenceChip` and `ExtrovertSummary` are shared, so their tint change affects marketing surfaces too. Those were not re-captured.
- The local dev server repeatedly stopped responding during long capture runs. Treat any surface without a screenshot as unverified.

# GRAVITRE UX RESET 1.0 — Phase 3 report

**Slice:** first product IA pass on Agents, Relationships, Performance, Settings, and Connectors. **No Motion polish (plan item 7).** No second AI runtime. No new prices, badges, or Enable toggles.

Pass language: **PASS / FAIL / NOT PROVEN / BLOCKED**.

Tip on `main`: `81937f28` (Phase 2 visual + Phase 3 chrome flatten). Follow-up: connector **list rows** (not topology cards stacked).

---

## Added

- Text hub links on Agents / Multi-agent / Training (replaces pill `HubTabs` on that strip).
- Closed “Evidence” disclosure under the Relationships map.
- Closed “Metrics” disclosure on Performance, after the attribution path.
- Connector list `variant="list"`: name, type/status, Details, overflow menu. Topology nodes stay for opt-in network view.

## Changed

- Agents fleet **default view = list** (team/graph remain available). Existing localStorage prefs keep the stored view.
- Connectors **default view = compact list**; network topology is opt-in.
- Settings preference rows: border-bottom rows instead of nested surface cards (Meson addon Enable blocks unchanged — those are real billing controls).

## Removed

- `ConnectorsAtmosphere` on `/agents` and `/connectors` (decorative canvas behind the job).
- Permanent KPI-first Performance layout.
- Permanent card stack around the Intelligence map.
- Mobile connector hub + card stack as the default list.

**Not removed:** graph/team views, connector topology toggle, settings sidebar, Intelligence Advanced tools, kill-switch, marketing isolation, Meson-as-not-chat, Meson addon Enable/Disable (authorized billing).

---

## A. Executive result

Phase 3 implements plan item 6 as a **chrome flatten**, not a rewrite of fleet/graph/connectors data.

Vercel production **READY** for `81937f28` — alias `gravitre.app` (`dpl_GRAwjH4iYXkQ2JMVferajqgv8gY9`). Authenticated click-through of every surface: **NOT PROVEN** (session expired in verification browser). Source + Vitest **PASS**.

Railway backend: not required (frontend-only).

---

## B. Per-surface

| Surface | Job | What changed |
| --- | --- | --- |
| `/agents` | Find a teammate | List first; no atmosphere; text hub nav |
| `/intelligence` | Understand relationships | Map first; evidence behind `<details>` |
| `/intelligence/performance` | Diagnose outcomes | Path first; metrics on demand |
| `/settings` | Change a preference | Rows, not card-per-group on the main page |
| `/connectors` | Connect a service | Compact list rows first; topology optional |

---

## C. Tests

Vitest `phase-3-product-ia.test.ts` (source + default prefs) — **PASS** 4 tests (2026-09-17).

Production authenticated PASS: **NOT PROVEN**.

---

## Customer-facing claims

No new prices, badges, Enable toggles, or certifications. Existing Meson addon Enable/Disable on settings was not introduced here.

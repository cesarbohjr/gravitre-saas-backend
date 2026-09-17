# GRAVITRE UX RESET 1.0 — Phase 3 report

**Slice:** first product IA pass on Agents, Relationships, Performance, Settings, and Connectors. **No Motion polish (plan item 7).** No second AI runtime. No new prices, badges, or Enable toggles.

Pass language: **PASS / FAIL / NOT PROVEN / BLOCKED**.

---

## Added

- Text hub links on Agents / Multi-agent / Training (replaces pill `HubTabs` on that strip).
- Closed “Evidence” disclosure under the Relationships map.
- Closed “Metrics” disclosure on Performance, after the attribution path.

## Changed

- Agents fleet **default view = list** (team/graph remain available).
- Connectors **default view = compact list**; network topology is opt-in.
- Settings preference rows: border-bottom rows instead of nested surface cards (Meson addon Enable blocks unchanged — those are real billing controls).

## Removed

- `ConnectorsAtmosphere` on `/agents` and `/connectors` (decorative canvas behind the job).
- Permanent KPI-first Performance layout.
- Permanent card stack around the Intelligence map.

**Not removed:** graph/team views, connector topology toggle, settings sidebar, Intelligence Advanced tools, kill-switch, marketing isolation, Meson-as-not-chat.

---

## A. Executive result

Phase 3 implements plan item 6 as a **chrome flatten**, not a rewrite of fleet/graph/connectors data. Live authenticated click-through of every surface: **NOT PROVEN** in this slice (source + Vitest).

---

## B. Per-surface

| Surface | Job | What changed |
| --- | --- | --- |
| `/agents` | Find a teammate | List first; no atmosphere; text hub nav |
| `/intelligence` | Understand relationships | Map first; evidence behind `<details>` |
| `/intelligence/performance` | Diagnose outcomes | Path first; metrics on demand |
| `/settings` | Change a preference | Rows, not card-per-group on the main page |
| `/connectors` | Connect a service | Compact list first; topology optional |

---

## C. Tests

Vitest `phase-3-product-ia.test.ts` (source + default prefs).

Production PASS / deploy: **not claimed**.

---

## Customer-facing claims

No new prices, badges, Enable toggles, or certifications. Existing Meson addon Enable/Disable on settings was not introduced here.

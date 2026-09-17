# GRAVITRE UX RESET 1.0 — Phase 3 report

**Slice:** first product IA pass on Agents, Relationships, Performance, Settings, and Connectors. **No Motion polish (plan item 7).** No second AI runtime. No new prices, badges, or Enable toggles.

Pass language: **PASS / FAIL / NOT PROVEN / BLOCKED**.

---

## Added

- Text hub links on Agents / Multi-agent / Training (replaces pill `HubTabs` on that strip).
- Closed “Evidence” disclosure under the Relationships map.
- Closed “Metrics” disclosure on Performance, after the attribution path.
- Connector list `variant="list"` + `data-gravitre-connector-row`: name, type/status, Details, overflow menu. Topology nodes stay for opt-in network view.
- Intelligence Advanced tools as **text links**, not a card grid.

## Changed

- Agents fleet **default view = list** (team/graph remain available). Existing localStorage prefs keep the stored view.
- Connectors **default view = compact list**; network topology is opt-in.
- Settings preference rows (security, notifications, model use-case, add-department, usage meters, overage): border-bottom rows instead of nested surface cards. Meson addon Enable blocks unchanged — those are real billing controls. API keys, webhooks, and department objects stay bounded because they are independently addressable records.

## Removed

- `ConnectorsAtmosphere` on `/agents` and `/connectors`.
- Permanent KPI-first Performance layout.
- Permanent card stack around the Intelligence map.
- Mobile connector hub + card stack as the default list.
- Advanced Intelligence icon-tile grid.

**Not removed:** graph/team views, connector topology toggle, settings sidebar, Intelligence Advanced tools (now text), kill-switch, marketing isolation, Meson-as-not-chat, Meson addon Enable/Disable (authorized billing).

---

## A. Executive result

Phase 3 implements plan item 6 as a **chrome flatten**, not a rewrite of fleet/graph/connectors data.

Source + Vitest **PASS** (5 tests, 2026-09-17). Playwright shots: Agents hub text links + Connectors list rows (harness). Authenticated production click-through: **NOT PROVEN**.

---

## B. Per-surface

| Surface | Job | What changed |
| --- | --- | --- |
| `/agents` | Find a teammate | List first; no atmosphere; text hub nav |
| `/intelligence` | Understand relationships | Map first; evidence behind `<details>`; Advanced is text |
| `/intelligence/performance` | Diagnose outcomes | Path first; metrics on demand |
| `/settings` | Change a preference | Rows for preferences; objects/billing keep bounds |
| `/connectors` | Connect a service | Compact list rows first; topology optional |

---

## C. Tests

Vitest `phase-3-product-ia.test.ts` — **PASS** 5 tests.

Playwright `Agents hub is text links; Connectors default is list rows` — run with the canonical spec (shots).

Production authenticated PASS: **NOT PROVEN**.

---

## Customer-facing claims

No new prices, badges, Enable toggles, or certifications. Existing Meson addon Enable/Disable on settings was not introduced here.

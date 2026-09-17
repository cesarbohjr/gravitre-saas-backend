# GRAVITRE UX RESET 1.0 — Phase 6 report

**Slice:** remaining page-purpose IA after Phase 3 (Workflows, Activity, Marketplace catalog chrome, Training, Intelligence hub, agent profile). Home widgets stay — they are independently movable dashboard objects. **No second AI runtime.** No new prices, badges, or Enable toggles.

Pass language: **PASS / FAIL / NOT PROVEN / BLOCKED**.

---

## Added

- Closed “Totals” / “Catalog” / “Operational totals” disclosures where counts were a second dashboard.
- Text hub links on Intelligence (same pattern as Agents).
- Text section links on Training and agent profile.

## Changed

- Workflows **default view = table**. Grid remains opt-in. Desktop/mobile still force grid on small screens via existing `isMobile` override.
- Marketplace type filters are **text**, not FilterChips. Search/price/department stay. Catalog tiles stay (discovery density).
- Training overview is type + numbered steps, not a gradient hero with step cards.
- Training datasets / jobs / fine-tunes sit in rows, not elevated `rounded-2xl` cards.

## Removed

- Activity KPI wrap (Selected / Filters / duplicate loaded counts — tabs already count).
- Workflows “N running” status banner.
- Intelligence `HubTabs` pill strip.
- Training `TabsList` + dataset-type tiles + duplicate six-metric strip.
- Agent profile pill tab bar and shadowed work-history cards.

**Not removed:** Home widget grid, Meson on workflows, marketplace pack tiles / PriceBadge / install, training job monitor numbers, agent Chat primary action.

---

## A. Result

Phase 6 is **source PASS** (Vitest `phase-6-remaining-ia.test.ts`). Authenticated production click-through: **NOT PROVEN**.

---

## B. Per-surface

| Surface | Job | What changed |
| --- | --- | --- |
| `/workflows` | Find and run work | Table first; totals on demand |
| `/activity` | Review what happened | Event list without a KPI dashboard |
| `/marketplace/assets` | Install capability | Text type filters; counts closed |
| `/training` | Configure training | Text sections; no card-first studio |
| `/intelligence*` | Hub nav | Text links |
| `/agents/[id]` | Configure one agent | Text sections; metrics on demand |

---

## C. Tests

Vitest Phase 6 — **PASS** (run locally with this slice).

Playwright Intelligence hub I11 updated from `tablist` to `navigation` + links.

Production authenticated PASS: **NOT PROVEN**.

---

## Customer-facing claims

No new prices, badges, Enable toggles, or certifications. Marketplace `PriceBadge` was not introduced here.

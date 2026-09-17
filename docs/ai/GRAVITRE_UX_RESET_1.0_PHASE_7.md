# GRAVITRE UX RESET 1.0 — Phase 7 report

**Slice:** leftover IA from Phases 5–6, then in-thread progressive disclosure (Sources / Execution / Artifacts). Same `useChat` owner. No second AI runtime. No new prices, badges, or Enable toggles.

Pass language: **PASS / FAIL / NOT PROVEN / BLOCKED**.

---

## Added

- Header **Ask Gravitre** on Training, Models, and Model Studio.
- Marketplace catalog publishes the install-target asset into `pageContext.selected`.

## Changed

- Workflows table default applies on small screens too (grid remains opt-in).
- Training drops the second Intelligence hub strip; learning loop is text links.
- Models registry / built-in, Model Studio stages, and Models catalog view are text nav.
- Model totals sit in a closed **Totals** disclosure.
- Thread sources, research cascade, tool list, artifacts, and multi-step execution sit behind `<details>` until opened. Confirm / fail / pending approval stay visible.

## Removed

- Mobile force-grid on Workflows.
- Gradient / card-first `LearningSurfacesCallout`.
- Duplicate Training + Intelligence hub on `/training`.
- Always-open research cascade card and always-visible tool chips for a single completed tool.
- Artifact kind pills / bordered artifact chips in chat.

**Not removed:** Intelligence in-page command bar (existing Intelligence composer), Home widgets, marketplace pack tiles / `PriceBadge`, pending-task approval chrome, BusinessOutcome in chat.

---

## A. Result

Phase 7 is **source PASS** (Vitest `phase-7-progressive-disclosure.test.ts` plus updated Phase 5–6 source tests). Authenticated production click-through: **NOT PROVEN**.

---

## B. Per-surface

| Surface | Job | What changed |
| --- | --- | --- |
| `/workflows` | Find and run work | Table first on all widths |
| `/training` | Configure training | One hub; Ask; text learning loop |
| `/marketplace/assets` | Install capability | Selected install asset in Ask context |
| `/models` | Registry | Ask; text tabs; totals closed |
| `/intelligence/model-studio` | Create / train | Ask; text stages |
| Canonical workspace | Answer then evidence | Sources / research / tools / artifacts closed |

---

## C. Tests

Vitest Phase 5, 6, 7 — **PASS** when this slice is run locally.

Production authenticated PASS: **NOT PROVEN**.

---

## Customer-facing claims

No new prices, badges, Enable toggles, or certifications. Marketplace `PriceBadge` was not introduced here.

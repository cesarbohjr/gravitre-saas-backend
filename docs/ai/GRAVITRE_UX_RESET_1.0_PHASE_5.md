# GRAVITRE UX RESET 1.0 — Phase 5 report

**Slice:** contextual Ask Gravitre on remaining product surfaces (plan item 5). Same runtime. No second `useChat`. No new prices, badges, or Enable toggles.

Pass language: **PASS / FAIL / NOT PROVEN / BLOCKED**.

---

## Added

- `setSelectedEntity` on `GravitreAIWorkspaceProvider` — publishes the current object without opening chat.
- `usePublishGravitreAISelection` so list/map/detail pages attach `pageContext.selected`.
- Header **Ask Gravitre** on Home, Marketplace catalog, agent profile, workflow detail, and connector detail.

## Changed

- Selecting a teammate, outcome, work object, approval, connector row, relationship node, or attribution path updates Ask context immediately (Ask then uses it).
- Proof harness Select Acme publishes before Open Gravitre.

## Removed

- The remaining “copy the page into chat” gap: Ask on those surfaces no longer depends on a prop that the page never set.

**Not removed:** `/ai` fullscreen, agent-chat scope, Intelligence composer, Meson-as-not-chat, marketing isolation, Settings preference rows (Ask is not the job of Settings).

---

## A. Result

Phase 5 is **source PASS** (Vitest `phase-5-contextual-ask.test.ts` + provider `setSelectedEntity` test). Authenticated production click-through: **NOT PROVEN**.

---

## B. Surfaces

| Surface | What Ask sees |
| --- | --- |
| `/home` | Page (header Ask) |
| `/marketplace/assets` | Page (header Ask) |
| `/agents` | Selected teammate |
| `/agents/[id]` | This agent |
| `/activity` | Explicitly selected outcome / work object |
| `/approvals` | Selected approval |
| `/workflows/[id]` | This workflow |
| `/connectors` | Focused list row |
| `/connectors/[id]` | This connector |
| `/intelligence` | Map selection |
| `/intelligence/performance` | Attribution path |

---

## C. Tests

- Vitest provider: `setSelectedEntity` does not open the workspace.
- Vitest Phase 5 source assertions.
- Playwright Ask Gravitre on proof: selection id `acme` is in debug **before** submit. Home header Ask added to the shots loop.

Production authenticated PASS: **NOT PROVEN**.

---

## Customer-facing claims

No new prices, badges, Enable toggles, or certifications.

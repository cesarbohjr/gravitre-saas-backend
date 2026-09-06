# GRAVITRE UI 3.0 — PHASE 7 BUILDER · DETAIL · GOLDENS

**Date:** 2026-09-06  
**Status:** **AWAITING CESAR ACCEPT**  
**Prior:** Phase 6 ACCEPTED (`26301c2f`)

---

## Scope (one pass)

Mineral density on deferred **builder/detail** surfaces + Phase 6 leftovers + Playwright visual scaffold.

| Surface | Change |
|---------|--------|
| Workflow detail | AutoStatusBadge → StatusChip + formatStatusLabel |
| Workflow builder | Decision/evaluating violet → `--g-signal`; theatrical purple glows removed; `--workflow-decision` → signal |
| Meson copilot | GlowOrb / StatusBeacon / ShimmerText out; PulseDot + NucleoIntelligence / NucleoClose |
| Run detail | Approval ping → PulseDot; batch panel StatusChip |
| Failure alerts | animate-ping → PulseDot |
| Agent detail / knowledge / memory | violet category → signal tokens |
| Connector detail + Add dialog | violet / blue-violet gradient → signal |
| Connectors hub leftovers | Bot / webhook Link2 → signal |
| Visual goldens | `e2e/visual/ui-3-0-shots.spec.ts` on shot harness (reduced motion) |

---

## Explicit non-goals

- Full Lucide→Nucleo eradication (cookie Cookie/Settings glyphs still Lucide; no Nucleo Cookie glyph yet)
- Committed PNG baselines in this ship (scaffold only — generate after accept: `pnpm exec playwright test e2e/visual --update-snapshots`)
- OAuth / connector auth rewrite
- Chat transcript density pass
- Invented health / latency / throughput metrics

---

## Scaffold honesty

No new customer prices, badges, Enable toggles, or fake TRAINED claims.

---

## Next (after accept)

**Phase 8+** — commit golden PNGs once local render is stable; remaining Nucleo; chat/knowledge chrome density as prioritized.

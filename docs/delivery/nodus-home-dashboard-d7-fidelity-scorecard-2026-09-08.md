# Home dashboard fidelity scorecard — D7 (2026-09-08)

**Target:** ≥9/10 vs Nodus home reference (literal recreation program)  
**Method:** Playwright fixture shot `/e2e/shots/home` @ 1280 / 1440 / 390  
**Rule:** No self-certify without screenshots + this scorecard filled

| Dimension | Weight | Score (0–10) | Notes |
|-----------|--------|--------------|-------|
| Compact title / header chrome | 1.0 | — | `GravitrePageHeader` scale |
| KPI row (4×1 density) | 1.5 | — | Default Operations preset |
| Workflow monitor table | 1.5 | — | Full-width below KPIs |
| Dual charts (agents + runs) | 1.5 | — | Donut + breakdown |
| Grid pad / gap / radius | 1.0 | — | `--np-*` tokens |
| Edit / presets chrome (secondary) | 0.5 | — | Not dominant in default |
| Type hierarchy | 0.75 | — | |
| Mobile (390) reorder affordances | 0.75 | — | ↑↓ in edit mode |
| Honest empty / real fixture values | 0.5 | — | No invented KPIs |
| Floating AI helper (off `/ai`) | 0.5 | — | Secondary FAB; separate from dashboard CTA |
| **Weighted total** | **10** | **—** | Fill after snapshot review |

## Harness

- Spec: `e2e/visual/nodus-product-fidelity.spec.ts` (`home` surface)
- Fixture route: `/e2e/shots/home`
- Fixtures: `/api/metrics/overview`, `/api/admin/ai-os/status`, learning/trust/impact paths in `apps/web/lib/e2e-shot-fixtures.ts`
- Snapshot dir: `e2e/visual/nodus-product-fidelity.spec.ts-snapshots/`

## Status

**INCONCLUSIVE** until baselines exist and a human fills scores from boards. Do not upgrade to PASS without evidence.

Refresh baselines (local Next + E2E flag):

```bash
pnpm exec playwright test e2e/visual/nodus-product-fidelity.spec.ts --update-snapshots
```

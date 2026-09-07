# Dashboard Fidelity Scorecard — P15 (2026-09-07)

**Target:** ≥9/10 per gate §25  
**Method:** Playwright fixture shots @ 1280 / 1440 / 390 vs Nodus Product Image crop  
**Rule:** No self-certify without screenshots + this scorecard filled

| Dimension | Weight | Score (0–10) | Notes |
|-----------|--------|--------------|-------|
| Sidebar (width, icons, active) | 1.5 | — | Sharp outline nav; hamburger-only expand |
| Page margins / pad | 1.0 | — | `--np-page-pad*` |
| KPI / metric shells | 1.0 | — | |
| Table / list density | 1.0 | — | |
| Chart / monitor blocks | 1.0 | — | |
| Radius / divide / shadow | 1.0 | — | `--np-radius*` / `--np-shadow` |
| Icon size / stroke | 1.0 | — | Nodus square-cap set |
| Type hierarchy | 0.75 | — | |
| Mobile (390) adapt | 0.75 | — | Bottom nav + drawer |
| Extension continuity | 0.5 | — | P13 compress (separate check) |
| **Weighted total** | **10** | **—** | Fill after snapshot review |

## Evidence pointers (fill on PASS)

- Playwright run / CI URL:
- Snapshot dir: `e2e/visual/nodus-product-fidelity.spec.ts-snapshots/`
- Comparison board paths:

## Status

**INCONCLUSIVE** until baselines exist and a human fills scores from boards. Do not upgrade to PASS without evidence.

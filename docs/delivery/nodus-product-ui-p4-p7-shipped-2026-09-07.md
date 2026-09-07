# Nodus product UI — P4–P7 shipped (2026-09-07)

**Status:** Shipped to `main` (await Vercel Ready + authenticated visual check)  
**Gate:** Cesar “move to p4+” after P1–P3

## Delivered

| Phase | Change |
|-------|--------|
| **P4** | Library under `apps/web/components/gravitre/nodus-product/`: Metric, Surface, PageHeader, Table*, Badge, Empty, Status; shared `PageHeader`/`StatCard` restyled to divide + `--np-*` |
| **P5** | Nucleo via `lib/icons.tsx` `nucleoByName` extended for sidebar keys (`team`, `waypoints`, `blocks`, `clipboardCheck`, `sparkles`); residual Lucide for unmapped chrome |
| **P6** | Agents orb selection + Workflows table/card shells on Nodus surface tokens |
| **P7** | Activity dual panes + Approvals queue/detail chrome on divide / `--np-shadow` |

## Scaffold honesty

**(a)** Explicitly authorized (“move to p4+”). No new prices, claims, badges, or Enable toggles.

## Evidence

- Deploy: cite Vercel Ready id after push.
- Visual PASS on Agents / Workflows / Activity / Approvals: **not claimed** until signed-in screenshots vs Product Image density.

# Nodus product UI — P14 + P15 shipped (2026-09-07)

**Status:** Shipped to `main` (await Vercel Ready)  
**Gate:** Cesar — fix Connectors header + rail chrome + sharp sidebar icons; start P14/P15; commit/push/deploy

## Bugfixes (same ship)

| Issue | Fix |
|-------|-----|
| Connectors header height | `PageHeader` description is full-width below title/actions (no 1-word column squeeze). Copy shortened to “Connected systems.” |
| Dual expand controls | Removed sidebar caret; top-bar hamburger is the only expand/collapse (desktop rail + mobile drawer) |
| Truncated logo | Full wordmark when expanded (`h-9`, max 168px); mark-only on collapsed rail; no caret stealing width |
| Soft/mixed sidebar icons | Sharp square-cap Nodus-style outlines for all primary nav `IconName`s |

## P14 — Marketing screenshots ← product captures

| Item | Detail |
|------|--------|
| Pipeline | `scripts/capture-product-shots.mjs` → `apps/web/public/product/app-*.png` |
| Consumers | `ProductScreenshot` / `ProductPreview` (`/product/app-*.png`) |
| Refresh | With local (or preview) server: `node scripts/capture-product-shots.mjs` |
| Honesty | Fixture shots only — captions already scope demo vs live metrics |

Binary PNG refresh runs against a live Next server; this commit ships chrome fixes + pipeline continuity. Re-capture after Ready if marketing frames must show the new rail/icons.

## P15 — Playwright fidelity pack

| Item | Detail |
|------|--------|
| Spec | `e2e/visual/nodus-product-fidelity.spec.ts` |
| Viewports | 1440×900, 1280×800, 390×844 (gate §25) |
| Surfaces | agents, workflows, approvals, connectors, activity, builder, ai |
| Scorecard | `docs/delivery/nodus-product-ui-p15-fidelity-scorecard-2026-09-07.md` |

Baselines: generate with `pnpm exec playwright test e2e/visual/nodus-product-fidelity.spec.ts --update-snapshots` after Next is up. **Not claimed PASS** until snapshots exist + scorecard filled from comparison boards.

## Scaffold honesty

**(a)** Explicitly authorized in this conversation (UI fixes + P14/P15 + deploy).  
No new prices, claims, badges, or Enable entitlement toggles.

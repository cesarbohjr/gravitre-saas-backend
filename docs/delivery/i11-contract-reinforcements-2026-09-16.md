# I11 — Contract reinforcements

**Date:** 2026-09-16  
**Status:** SHIPPED (code)

## Plan reinforcement (spec Revision 3)

Added I11–I13 after I10 so the rebuild cannot silently regress:

- **I11** (this ship): CI + unit/e2e contracts
- **I12:** live G1/G4/G8 + a11y scan (not this commit)
- **I13:** graph density / LOD

## Delivered

- `scripts/check-intelligence-customer-surface.mjs` — bans admin Intelligence imports and raw `INSUFFICIENT_DATA` / `NOT_CONFIGURED` unless mapped through quality copy
- CI step **Intelligence customer surface guard**
- Learning relationships inspector no longer imports `/admin/intelligence`
- ERROR lens metrics are `—` / “Unable to load intelligence”, never `0`
- Hub contract tests: 7 tabs, Training folded to Model Studio
- Playwright: hub tabs, List view, Reports templates + honest scheduled empty

## Verification

- Local: `vitest run __tests__/intelligence/i11-hub-contract.test.ts` + customer-surface guard
- G1/G4/G8 live: still **NOT RUN** (I12)

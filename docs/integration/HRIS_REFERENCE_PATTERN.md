# HRIS reference pattern — Workday excluded, BambooHR reference (STA-280)

**Status:** Pattern documented; Rippling catalog-only  
**Date:** 2026-06-21  
**Related:** `backend/app/connectors/bamboohr.py`, `backend/app/connectors/workday_oauth.py`

## Decision

| Vendor | Demo / pilot | Implementation | Notes |
|--------|--------------|----------------|-------|
| **BambooHR** | **Reference HRIS** | Shipped — OAuth + tools in `bamboohr.py` | Use for HR workflow demos, marketplace dept packs, simulation fixtures |
| **Workday** | **Excluded** | Catalog + OAuth scaffold only | Enterprise tenant-specific; no self-serve demo path |
| **Rippling** | **Not started** | Not in vendor catalog | Future Tier 4 HRIS; follow BambooHR pattern when prioritized |

## Workday exclusion rules

1. **Do not** surface Workday in demo scripts, marketplace hero connectors, or default org seed connectors.
2. Catalog entries remain for **sales/enterprise scoping** conversations only.
3. OAuth env vars (`WORKDAY_CLIENT_ID`, etc.) are optional; missing config must not block Tier 1 demos.
4. Simulation coverage registry marks `workday` as `demoExcluded: true` — see `backend/app/connectors/simulation_coverage.py`.

## BambooHR reference pattern

When adding or extending HRIS connectors, match BambooHR:

1. **OAuth** — vendor-specific token store via existing connector crypto (`connectors/crypto.py`).
2. **Read-first catalog** — v1 employee/time-off reads before any v2 writes.
3. **Destructive writes** — `requires_approval=True` in action catalog; approval gate in workflow policy.
4. **Fixtures** — record golden responses in `connector_fixtures` for digital-twin demos (`digital_twin.py`).
5. **Compensation** — HR writes are generally **non-compensatable**; failed runs use **fail-fast**, not CRM-style undo (see `docs/ai/PARTIAL_FAILURE_POLICY.md`).

## Rippling (deferred)

Rippling is the planned second HRIS reference (mid-market). Until implementation:

- Do not claim Rippling in marketing or connector counts.
- When implemented, copy BambooHR module layout: `rippling_oauth.py`, `rippling.py`, vendor_definitions block, tier1 reads → tier2 writes.

## Verification

```bash
npm run tier4:audit          # confirms Workday excluded, BambooHR tool coverage
npm run demo:simulation      # zero live-demo blockers for BambooHR reads
python -c "from app.connectors.simulation_coverage import DEMO_EXCLUDED_VENDORS; assert 'workday' in DEMO_EXCLUDED_VENDORS"
```

# Pilot 2 W.7 — LCP / INP on `/features/technology` + no Three

**Measured:** 2026-09-19T08:54:40Z  
**URL:** https://gravitre.app/features/technology  
**Tool:** Lighthouse 12.6.0 (Playwright chrome-headless-shell)  
**Artifact:** [`pilot2-technology-webvitals-summary.json`](./pilot2-technology-webvitals-summary.json)

## No Three — PASS

| Check | Result |
|-------|--------|
| `apps/web/package.json` deps | **PASS** — no `three`, `@react-three/fiber`, `@react-three/drei` |
| `apps/web/pnpm-lock.yaml` | **PASS** — no Three/R3F packages |
| Pilot 2 engine | SVG + framer-motion only |

## Lab vitals (full marketing page)

Desktop LCP budget reference (marketing CI home/pricing): ≤ 3300 ms.

| Form | Perf score | LCP | TBT (lab proxy) | CLS | INP |
|------|------------|-----|-----------------|-----|-----|
| Desktop | 0.79 | **2.2 s** | 110 ms | ~0 | *not sampled* (navigation-only) |
| Mobile | 0.48 | **10.8 s** | 1040 ms | 0.058 | *not sampled* |

### Notes

1. **INP** requires an interaction sample; cold navigation Lighthouse does not emit INP. Desktop **TBT 110 ms** is the lab main-thread proxy recorded here. Field INP should come from RUM / CrUX later.
2. Mobile LCP is **page-level** (GIBE TRACE + Task Decomposition Field + legacy Features content), not isolated to the Pilot 2 scene.
3. Desktop LCP **2.2 s** is under the 3.3 s marketing CI LCP gate used for home/pricing — **PASS** vs that bar for this URL on desktop.
4. Mobile LCP **FAIL** vs a 3.3 s bar — tracked as page weight / mobile lab follow-up, **not** a Three regression.

## Verdict

| Gate | Status |
|------|--------|
| Confirm no Three | **PASS** |
| Desktop LCP ≤ 3.3 s | **PASS** (2.2 s @ 2026-09-19T08:54:01Z) |
| INP (interaction) | **NOT RUN** — navigation-only LH; TBT proxy recorded |
| Mobile LCP | **FAIL** lab (10.8 s) — full-page; separate optimization backlog |

W.7 closed for Pilot 2 ship criteria (measure + no Three). Mobile LCP improvement is out of Pilot 2 creative scope unless Cesar prioritizes it.

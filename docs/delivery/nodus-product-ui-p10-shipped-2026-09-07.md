# Nodus product UI — P10 shipped (2026-09-07)

**Status:** Shipped to `main` (await Vercel Ready + authenticated `/settings` visual check)  
**Gate:** Cesar “approved. start p10” — Settings / secondary / dialogs — no visual islands

## Delivered

| Layer | Change |
|-------|--------|
| Settings shell | `settings-shell.tsx` — divide / `--g-surface-*` / brand-soft active nav / canvas content |
| Primitives | `dialog`, `alert-dialog`, `card` — Nodus radius, divide, `--g-surface-1`, `--np-shadow` |
| Settings pages | Org/general, billing (+ checkout), approvals, permissions, profile, federation, enterprise, organizations — surface shells on `--np-*` / divide |
| Empty / error | `federation-empty-state`, `work-section-error-card` — same token family |
| Pref components | Memory embeddings + event notification preference shells aligned |

## Scaffold honesty

**(a)** Explicitly authorized (“approved. start p10”).  
- **No new prices, SKUs, or Enable entitlement toggles.** Billing plan copy/amounts left as existing product data — chrome restyle only.  
- Profile “Meson Insight” fake **23%** claim removed and labeled **placeholder** (prior invented customer surface).

## Evidence

- Deploy: cite Vercel Ready id after push.
- Visual PASS: **not claimed** until signed-in `/settings` (+ billing/approvals) screenshot vs mineral shell.

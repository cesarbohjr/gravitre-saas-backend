# Nodus product UI — P11 shipped (2026-09-07)

**Status:** Shipped to `main` (await Vercel Ready + mobile visual check)  
**Gate:** Cesar “approved. move to p11” — Mobile adapt (drawer / bottom nav; tables → cards; progressive disclosure)

## Delivered

| Layer | Change |
|-------|--------|
| Bottom nav | `mobile-bottom-nav.tsx` — Home / Chat / Agents / Activity / Approvals; `md:hidden`; Nodus tokens; drawer keeps full nav |
| App shell | Main padding clears bottom nav; builder path exempt |
| Tables → cards | `AdaptiveDataView` + `DataTable` mobileFallback (auto cards); divide/surface chrome |
| Workflows | Force grid below `md`; hide table segment control on phones |
| Activity | List ↔ detail swap on mobile (Approvals pattern) + Back |
| Approvals | Sticky Approve/Reject sits above bottom nav |

## Scaffold honesty

**(a)** Explicitly authorized (“approved. move to p11”).  
No new prices, claims, badges, or Enable entitlement toggles. Bottom tabs are existing `APP_ROUTES` only.

## Evidence

- Deploy: cite Vercel Ready id after push.
- Visual PASS: **not claimed** until signed-in phone-width check of shell + Activity/Workflows.

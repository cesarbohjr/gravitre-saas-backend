# GRAVITRE × NODUS — PHASE 8 (app shell PLATFORM-ADAPT)

**Date:** 2026-09-07  
**Status:** **IMPLEMENTED**  
**Prior:** Phase 7 auth chrome @ `68295537`

## Goal

Apply Nodus light-first material to the authenticated product chrome without changing auth, billing gates, or nav hrefs.

## What changed

| Surface | Change |
|---------|--------|
| `app-shell.tsx` | White canvas + charcoal type |
| `sidebar.tsx` | Gray rail (`--g-background`), `border-divide`, light logos only (no `dark:` swaps), brand footer chip |
| `sidebar-nav-link.tsx` | Active = brand left border + soft green wash |
| `top-bar.tsx` | White bar + `shadow-aceternity` + divide borders; remove ThemeToggle; Admin/Lite Nodus pills |
| `global-command-bar.tsx` | Divide border + aceternity shadow on search chip |

## Explicitly unchanged

- Auth / billing / trial banners / redirects in `AppShell`
- Sidebar nav config hrefs and Lite/Admin seat logic
- Meson toolbar, notifications, org switcher behavior

## Scaffold honesty

**(a)** Platform-adapt of shell to licensed Nodus tokens authorized (Phase 8).  
No new prices, claims, or Enable toggles.

## Next

Phase 9 — Desktop + extension denser adapt to same tokens.

# GRAVITRE UI 3.0 — PHASE 4 WEB APP SHELL

**Date:** 2026-09-06  
**Status:** **AWAITING CESAR ACCEPT** (pre-accept polish landed)  
**Prior:** Phase 3 ACCEPTED · Phase 4 shell on `main` (`f88f793e`)

---

## What landed (shell)

| Surface | Change |
|---------|--------|
| `app-shell.tsx` | Mineral `--g-canvas` root · Nucleo close |
| `sidebar.tsx` | Mineral surface + hairline border; denser logo row (`h-12`) |
| `sidebar-nav-link.tsx` | Active = emerald edge + `--g-surface-active` |
| `top-bar.tsx` | Mineral bar; denser height; quieter account header |
| `global-command-bar.tsx` | Calm mineral panel · Nucleo via `Icon` overrides |

ThemeProvider light/dark **kept**. Nav IA unchanged. No hub page rewrites.

---

## Pre-accept polish (2026-09-06)

| Item | Change |
|------|--------|
| Nucleo chrome | Marketing nav/CTAs + shell `Icon` overrides for search/menu/command/bell/close/chevron/nav semantics |
| Motion | `LivingMineralField` — drifting mineral washes + Intent→Verified TracePath (not dark IntelligenceField grid) |
| Domain | Must alias `gravitre.app` / `www` to latest Ready production deploy (auto-assign drifts) |

**Honesty:** Full Lucide eradication deferred; marketing chrome + Phase 4 shell prefer Nucleo. Cookie consent still uses Lucide Cookie/Settings glyphs until Nucleo matches land.

---

## Explicit non-goals

- Dashboard composition redesign (Phase 5)  
- Full Nucleo migration of every Lucide import  
- Playwright goldens  

---

## Accept → next

Approve Phase 4 → Phase 5 core product surfaces (Agents / Workflows / GIBE / Approvals).

**Prod PASS bar:** Ready deploy + `gravitre.app` alias + live daylight screenshot (not Pass 3 void).

# GRAVITRE × NODUS — PHASE 9 (desktop + extension denser adapt)

**Date:** 2026-09-07  
**Status:** **IMPLEMENTED**  
**Prior:** Phase 8 app shell @ `b19302b7`

## Goal

Same Nodus light-first token contract on desktop Tauri and browser extension (denser spacing, divide borders, aceternity shadow, brand green).

## What changed

| Surface | Change |
|---------|--------|
| `apps/desktop/src/styles.css` | Full Nodus token set; gray chrome / white canvas; denser spacing; brand CTAs; aceternity elevation |
| `apps/extension/popup.css` | Compact Nodus popup (shared by sidepanel) |
| `apps/extension/content/overlay.css` | Overlay panel uses charcoal/gray/brand tokens; slate blues removed |

## Explicitly unchanged

- Desktop session/auth/API logic (`App.tsx`, `lib/*`)
- Extension content scripts / background handlers
- No invented prices or claims

## Scaffold honesty

**(a)** Cross-platform consistency authorized (Gate 0 + Phase 9 go).

## Next

Phase 10 — Residue audit (Notus/orange/fake claims/demo logos still in unused nodus components).

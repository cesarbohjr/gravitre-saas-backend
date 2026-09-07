# Nodus product UI — P12 shipped (2026-09-07)

**Status:** Shipped to `main` (await Vercel Ready + desktop visual check)  
**Gate:** Cesar “approved p11, now start p12” — Desktop densify (denser panes, shortcuts, context menus)

## Delivered

| Layer | Change |
|-------|--------|
| Tokens | `--np-page-pad` 16, `--np-row-h` 36, tighter KPI gap / header |
| PageHeader / StatCard / Metrics | Tighter chrome; home full-width ops canvas |
| DataTable | Row height bound to `--np-row-h` |
| Shortcuts | ⌘B rail toggle; ⌘N → workflows new builder |
| Context menus | Workflow cards, Activity rows, Approvals queue (existing actions only) |
| Agents / Approvals / Activity | Less showcase padding; denser panes |

## Scaffold honesty

**(a)** Explicitly authorized (“approved p11, now start p12”).  
No new prices, claims, badges, or Enable entitlement toggles. Shortcuts/menus only wire existing routes and actions.

## Evidence

- Deploy: cite Vercel Ready id after push.
- Visual PASS: **not claimed** until signed-in desktop check (home/agents/workflows + ⌘B / right-click).

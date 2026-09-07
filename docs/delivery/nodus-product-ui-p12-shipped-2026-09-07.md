# Nodus product UI — P12 shipped (2026-09-07)

**Status:** Shipped to `main` — Vercel Ready  
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

- Deploy READY: `dpl_4paZHYNHX7s9RfHNUyeugS5K59pM` @ tip `f6cd76a1` (production alias `gravitre.app`)
- Visual PASS: **not claimed** until signed-in desktop check (home/agents/workflows + ⌘B / right-click).

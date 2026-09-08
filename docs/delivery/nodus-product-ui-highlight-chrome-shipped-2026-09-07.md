# Nodus soft highlight chrome — shipped (2026-09-07)

**Status:** Shipped to `main` (await Vercel Ready)  
**Gate:** Cesar — apply Product Image highlight colors, pill shape, and type across web app surfaces

## What landed

| Layer | Change |
|-------|--------|
| Tokens | `HIGHLIGHT` / `CHIP` / soft `STATUS` (+ `paused`); `TYPE` uses `--g-text-*` + table roles |
| Signal soft | `--g-signal-soft: #e8f1fb` (Llama-style blue chips) |
| Primitives | `Badge`, `StatusChip`, `StatusBadge`, `GravitreBadge`, `HighlightChip`, table Th/Td |
| Surfaces | Connectors readiness/Available/filters, Sources status, Workflow deps, chat step badges / selectors |
| CSS utils | `.g-chip` + `.g-highlight-*` for ad-hoc call sites |

## Design rule

Soft fill + strong text + `rounded-full` — never solid primary blocks for tags. Status column may use `StatusChip appearance="plain"` (dot + graphite label).

## Scaffold honesty

**(a)** Explicitly authorized (“same highlighted colors, shape and design on all web app surfaces”).  
No new prices, claims, badges, or Enable entitlement toggles — visual system only.

## Not claimed

Authenticated visual PASS until Ready + spot-check on `/connectors`, `/agents`, `/approvals`.

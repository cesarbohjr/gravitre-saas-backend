# Design System Review — v0 vs Gravitre

## Shell Alignment
Cursor app shell already defines:
- Sidebar navigation groups
- Top bar with org + environment visibility

v0 must preserve this layout and label structure without adding new nav groups.

## Token Compatibility
Cursor styling is aligned to the Gravitre brand spec (Inter font, muted borders, card‑based layout).
Any v0 design must use the same token semantics:
- `--bg`, `--surface`, `--text`, `--action`, `--highlight`
- Inter font (no alternate fonts)

## Component Mapping

| v0 Component | Cursor Alignment |
|---|---|
| AppShell / Sidebar / TopBar | `apps/web/components/app-shell.tsx` |
| StatusBadge | Run status badge patterns (local) |
| EnvironmentBadge | Inline environment badges (text + muted pill) |
| DataTable | Existing `<table>` patterns |
| SessionItem | `OperatorSessionItem` |
| ReasoningBlock | `ReasoningBlock` |
| ActionCard / ActionProposal | `ActionProposalCard` |
| ContextPack | `ContextPackCard` |
| GuardrailsBox | `ContextPanel` + `GuardrailBadge` |
| VendorLogo | Not present in Cursor |

## Accessibility & States
Cursor pages already implement:
- loading / empty / error states
- keyboard focus on links/buttons
- role/aria labels on tables and dialogs

v0 designs must include:
- Loading/empty/error states for new cards or panels
- Clear focus states for interactive elements
- No low‑contrast text in dark theme

## Gaps to Resolve in v0
- v0 adds stats cards and filter bars on Workflows that aren’t in Cursor.
- v0 uses “Connectors” nav; Cursor canonical is “Integrations.”
- v0 should avoid introducing canvas drag‑drop (not in scope).

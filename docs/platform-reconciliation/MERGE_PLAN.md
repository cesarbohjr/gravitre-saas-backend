# Merge Strategy — v0 into Cursor

## Goals
- Keep Cursor as the canonical runtime (backend + API).
- Use v0 as **visual alignment only**; do not introduce new routes or layouts.
- Preserve Gravitre app shell, environment visibility, and safety model.

## Component Adoption
Adopt v0 component visuals only when they map cleanly to existing Cursor components:
- AppShell / Sidebar / TopBar → keep Cursor structure; apply v0 styling if needed.
- Status / Environment badges → map to existing badge patterns.
- Action cards / Context packs → map to operator components.
- Data tables → reuse existing tables (no new DataTable framework).

## Page Migration Rules
1) **Workflows**  
   - Keep current list layout; avoid v0 stats/filter bars unless backed by data.  
   - Use orchestration preview already implemented in Cursor.
2) **Runs**  
   - Use existing list + detail views; add any v0 visualization only if it matches run step data.
3) **Approvals**  
   - Keep current table and add gate labels only.
4) **Agents**  
   - Keep registry + versioning; do not turn into workflow builder.
5) **Integrations**  
   - Retain `/integrations` naming; remove `/connectors` in v0.
6) **Sources**  
   - Canonical UI under `/rag/sources`; `/sources` can be a redirect.
7) **Admin (Environments/Settings)**  
   - v0 can design placeholders, but BE required before full UI.

## Design Token Integration
Align v0 colors, spacing, and typography to `docs/brand/Gravitre_Brand_Alignment_Spec.md`.
Cursor already uses shadcn/ui and tokenized styles; v0 must match these tokens.

## Recommended Merge Order
1. App shell / navigation alignment (remove connectors, ensure correct route names).
2. Workflows + Runs + Approvals (orchestration + execution flow).
3. Agents + Operator console (role tags + link visualization).
4. Integrations + Sources (ensure routing consistency).
5. Admin surfaces (Environments, Settings) after BE definition.

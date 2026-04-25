# Frontend Source of Truth

The v0 frontend imported from `gravitre-saas-interface` is the canonical UI for Gravitre.

## Rules

- Active frontend path is `apps/web`.
- The previous Cursor-generated frontend is archived at `archive/old-cursor-frontend/apps-web-cursor`.
- Archived frontend is reference-only and must not be reused in active UI unless explicitly approved.
- Do not mix archived UI pages, components, layouts, styles, routes, or mock data into the active frontend without explicit approval.
- Backend logic remains unchanged and stays in `backend/`.
- Backend integration should connect the v0 frontend through API proxy routes.

## Scope Notes

- This change only establishes frontend source-of-truth and import location.
- API wiring and UI redesign are intentionally out of scope for this step.

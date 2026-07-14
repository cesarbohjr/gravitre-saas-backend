# Apollo plan upgrade — human decision (BYPASSED for platform smoke)

**Decision (2026-07-14):** Treat company/contact **discovery** as **BYO-tier** — same honesty bar as ZoomInfo / LinkedIn Sales Navigator. Tenants bring an Apollo plan that includes People/Companies search API access. Platform smoke does **not** wait on upgrading the smoke-org free plan.

## What works vs what requires BYO search plan

| Capability | Free / basic connected Apollo | Paid plan with search API |
|---|---|---|
| Create list (`apollo.lists.create`) | Typically **works** | Works |
| Company search (`apollo.organizations.search`) | **Blocked** (known free-plan 403) | Works |
| Contact search (`apollo.people.search`) | **Blocked** (known free-plan 403) | Works |
| Build ICP / HubSpot list sync | Works without Apollo search | Works |

## Product surfaces (labeling — not executor changes)

- Marketplace / install checklist: `requirementNote` + live `discoveryLimitation` when probe sees free-plan 403
- Connector availability: capability notes + optional force-live probe
- Workflow/chat errors: `format_tool_error_for_user` maps `apollo_plan_limit` / free-plan body →  
  `Company/contact discovery requires an Apollo plan with search API access — see https://app.apollo.io/ to upgrade`
- Evidence: `docs/delivery/apollo-discovery-byo-labeling-live.json`

## Runtime notes

- Runtime already prefers connector `api_token` / `api_key` over OAuth when both exist; free-plan 403 maps to `permission_denied` (`apollo_plan_limit`).
- Free-plan 403 → `permission_denied` (`apollo_plan_limit`), not `auth_expired`
- Re-run discovery labeling smoke: `python scripts/smoke-apollo-discovery-byo-labeling-live.py`
- Re-run Sales E2E: `python scripts/smoke-phase4-sales-workflow-e2e-live.py`

## Optional later (Option A)

Upgrading the smoke-org Apollo plan would make discovery live without reverse-engineering labels — the BYO notes remain accurate for other free-plan tenants.

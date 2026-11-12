# Agency Agents — Full Suite Engineering and Release Contract

Status: **Engineering workstream opened; NOT deployed or certified.**

## Source of truth
- Reuse the pinned MIT-source, 283-profile, 18-division inventory in `backend/app/marketplace/agency_agents_inventory.json`.
- Preserve existing reviewed role implementations, enrichment targets and Marketplace seed/catalog/install paths. No second marketplace, no duplicate default agents.
- PR #581 remains owner of the existing governed native-runtime/browser-adapter certification; PR #587 remains owner of shared One Brain intelligence/voice. This workstream owns remaining **Agency Agents full-suite role packaging, governed publication, activation and certification** only.
- Do not move Qualified Prospecting Play ownership from PR #590.

## Ordered engineering gates
1. **Reconciliation:** Audit all 283 pinned profiles, existing approved roles, catalog/operator/pack collisions, source-license/hash checks and live-install differences. Produce a machine-readable disposition report per role: enriched existing, approved specialist, gated review, excluded, with rationale.
2. **Role packaging:** Build reviewed agent configuration and versioned department packs through canonical Marketplace assets. Never import upstream text as privileged instructions. Require explicit capabilities, tool allowlists, least-privilege grants, connector dependencies, cost limits and visible role descriptions. No blanket publication of 283 roles.
3. **User experience:** Public Marketplace discovery, division filters, readiness prerequisites, pricing/entitlements, install/upgrade/rollback, disabled/no-connector explanations, role-specific run entrypoints, run status and observable results. Confirm MSP tenant boundaries and client account attribution.
4. **Governed runtime:** Use canonical intelligence, context, sentiment, memory, text/voice and execution APIs; preserve native approvals, cancellation/revocation, idempotency and authorization. Verify cross-tenant rejection, prompt-injection containment, connector health and unavailable-provider fallback.
5. **Certification:** Automated role-by-role manifest validation and smoke scenario coverage, negative write tests, tenant RLS, installation rollback, tool invocation evidence, error/recovery evidence, exact-head CI. Each profile gets a recorded status: not implemented / packaged / offline-pass / live-pass; never mark skipped or untested profiles as certified.
6. **Release:** After green CI and review, deploy initially disabled or limited to controlled acceptance tenant; run authenticated production smoke for representative agent families; publish only expressly approved, tested profiles. Separate launch authorization for high-risk finance/healthcare/security and any external writes.

## Completion evidence
- Role-by-role approved manifest and collision disposition for all 283 entries.
- Reproducible test commands, immutable commit SHA, GitHub Actions URLs, signed/sanitized reports, actual success/failure counts, and explicit skipped tests.
- Marketplace availability checked through the user interface and server API, not inferred from seed definitions.
- No production rollout or live outreach without separate release permission.

## Non-goals
- No changes to voice transport in PR #587, browser-adapter certification in PR #581 or Qualified Prospecting Play in PR #590.
- No claim that the full suite is deployed from adding this engineering contract.

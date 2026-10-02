# Marketplace 3.0 department surfaces

All eight canonical department packs use a department workspace: MSP Service Desk, Security Operations, Revenue Operations, Customer Success & Support, Finance Operations, Marketing Operations, People/IT Operations, and Executive Command Center.

Installed packs open `/marketplace/departments/<slug>` from the installed-pack inspector. Overview retains each installed version's dashboard metric and trend choices; Plays, Evidence, Data & standards, and Agents & activity expose the matching contracts and installed runtime entities. Existing department pipeline/funnel charts remain in the inspector.

The backend requires tenant membership and an active install, pins the installed asset version, and reads only that tenant's installed workflows and sources. Charts accept independently verified business measurements linked to completed production executions. Empty data stays unavailable. Catalog certification is labeled separately from tenant results.

Platform administrators can preview all department blueprints from Marketplace platform administration, choose an authorized pilot tenant, install in Observe mode, submit stored production run/outcome IDs, and publish only when fresh readiness permits it. Backend governance, entitlements, connector checks, capability review, and evidence verification remain authoritative. Stale catalog certification cannot enable publication.

Validation: backend contract/version/tenant isolation and route authorization tests; full frontend tests; TypeScript and changed-surface lint; desktop (1440px) and mobile (390px) checks of all eight departments and five tabs, search, empty evidence, all rollout previews, and stale-proof publication gating. Fixture screenshot routes are production-gated and contain no customer data. Reproduce browser assertions with `playwright.visual.config.ts` and `e2e/visual/marketplace3-departments.spec.ts`.

This delivery completes the UI and integration surfaces. Production Verified and Outcome Verified still require actual tenant production executions, independent source evidence, measured baselines/results, and fresh certification. A screenshot fixture or passing regression suite does not satisfy those gates.

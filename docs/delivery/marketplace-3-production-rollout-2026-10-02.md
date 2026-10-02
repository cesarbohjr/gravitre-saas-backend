# Marketplace 3.0 rollout and live evidence collection

PR #290 merged after backend, web, dependency, runtime, department evaluation,
and integration smoke gates passed. The production catalog now contains all
129 Marketplace 3.0 assets, 129 matching versions, and 121 component links.
All eight Outcome Packs are governed/internal/draft with publishReady false.
The 76 existing marketplace assets were preserved. There are 65 Plays, 24 agents,
eight datasets, eight dashboards, eight knowledge packs, and eight capability
packages in the new catalog, plus the eight parent Outcome Packs.

The final installation audit exposed a staging deadlock: a draft could not be
installed to collect production proof, and linked capability companions also
remained drafts. The platform-admin pilot endpoint now admits only global
internal Marketplace 3.0 draft Outcome Packs whose current contracts pass
fixture checks and governance validation. It uses the existing installer and
records pilot metadata, without publishing or certifying the parent.

## Pilot and certification sequence

1. Authenticate as a platform admin. Choose an explicit authorized tenant UUID
   with the required sources connected and enough plan capacity.
2. Call `POST /api/marketplace/platform/assets/{slug}/marketplace3/install-pilot`
   with `{"orgId":"<tenant UUID>","installVariables":{}}`. The route rejects
   extra fields such as force. Ordinary tenant installs still reject drafts.
   The administrative pilot bypasses the marketplace purchase check while
   retaining tenant plan limits, connector checks, binding checks, component
   rollback, and runtime review/approval. Plays start in OBSERVE mode.
3. Review installed capability packages through the existing runtime review
   process. Only directly linked internal draft companions from the same
   publisher are admitted as bundle dependencies. Installation does not approve
   or publish those packages. The same dependency resolution supports a later
   evidence-certified published parent without exposing standalone drafts.
4. Run the actual installed workflows with real record IDs and tenant policies.
   Authorize consequential writes through the existing approval process.
   Preserve source-verifier snapshots for any advertised writes. Synthetic,
   predicted, dry-run, or digital-twin steps do not provide production proof.
5. Call the existing certification endpoint with runtimeEvidence entries shaped
   as `{"hubspot":{"orgId":"<tenant UUID>","runIds":["<stored run UUID>"]}}`.
   Include every required provider; successful stored steps must cover every
   advertised action. A tested profile earns Production Verified from resolved
   live proof without manually asserting production status in its config.
6. For Outcome Verified, provide outcomeEvidence shaped as
   `{"orgId":"<tenant UUID>","eventIds":["<stored event UUID>"]}`. The event must
   be a canonical VERIFIED SUCCESS business result with a measured baseline and
   result, source records, verification method, and production execution. Its
   Play, outcome event, and KPI must match the pack. An event name alone is not
   evidence.
7. Promote with the existing marketplace3/promote endpoint only when the fresh
   database-resolved evidence gate passes. Promotion rechecks stored proof.

## Observed live blockers

At rollout, Marketplace 3.0 had zero tenant installations and zero canonical
play_business_result measurements. Freshservice had no connection. BambooHR
needed connection; QuickBooks and Zendesk awaited authentication. HubSpot had
healthy and pending-auth connections, and Stripe had an active connection.
These are aggregate statuses across tenants, not proof that any chosen tenant
has all required sources or that the advertised actions succeed.

Dataset schemas remain normalized contracts rather than new ingestion adapters.
Knowledge standards install as metadata pending tenant upload; their guidance
is also embedded in agent and Play instructions. Neither catalog seeding nor
pilot installation produces a baseline or proves a business improvement.

Regression validation: 725 Marketplace, route, signature, readiness, seed,
installation, pilot authorization, and certification tests pass.

# PR581 approved first tranche — existing-agent enrichments

The user approved these four enrichments in the PR581 continuation. This approval covers code and certification on the existing feature branch. PR581 remains open; no merge, publication, install into a live organization, migration or deployment is performed.

| Upstream role | Existing Marketplace agent | Required existing connector |
|---|---|---|
| Content Creator | `content-writer` | HubSpot |
| SEO Specialist | `seo-analyst` | Google Analytics |
| Discovery Coach | `sdr-coach` | HubSpot |
| Support Responder | `ticket-triage` | Zendesk |

## Runtime and provenance

`app/capabilities/agency_enrichment.py` contains four curated, bounded workflow definitions. Each stores an immutable source revision, source path, source SHA-256, MIT marker, approval reference and guidance version. No upstream instruction text, scripts, tool policy or autonomous permissions are imported. Guidance is advisory; connector IAM, tenant scope, paid entitlement, plan limits and write approvals remain authoritative. Existing prices, models, persona keys, capabilities and connector systems are retained. SEO’s existing Analytics system is now an explicit install prerequisite, and the guidance explicitly distinguishes Analytics evidence from search ranking/keyword data.

Only these four existing catalog slugs receive an `agency_enrichment` reference. Both existing prompt builders resolve the exact approved reference to vetted code. Unknown versions, changed provenance, wrong agent slugs and injected persisted guidance render nothing. Old snapshots without the reference receive no enrichment: rollback actually removes the role guidance. Existing installed agents change only through their normal explicit install/upgrade path; titles never globally activate a new role.

`approved_marketplace_candidates()` returns these existing assets only. The source census remains a proposed inventory; the other 279 roles have no enrichment approval. No separate Agency Agents listings or default personas are created.

## Lifecycle and tenant safeguards

The approved catalog refresh preserves the previous snapshot, inserts a monotonically numbered version, then advances the live pointer with an expected-version check. Repeated identical refreshes are inert. A concurrent pointer change fails closed; a pending snapshot never becomes the active config by itself. Foreign publisher or tenant-owned slug collisions are rejected. This version-preserving behavior is limited to the four approved assets; unrelated seed behavior is unchanged.

Installation continues through `install_asset()` and the canonical operator/agent/install tables. Reinstalls keep stable per-org IDs, preserve admin-reduced or revoked tool grants, and count an existing operator as a replacement rather than a new quota slot. Internal/private assets are now rejected for foreign organizations before preview probes, connector checks or writes, including force installs. Public assets remain shared. Org-owned listing rollback uses the existing version API. Public-agent rollback uses the existing install endpoint with an optional positive integer `versionNumber`: it restores that organization’s agent from a published historical snapshot without changing the shared listing. Current listing entitlement/visibility remains authoritative, snapshot connector prerequisites are checked, future or unpublished versions are denied, and connector grants are preserved. Pending snapshots remain unpublished until the live catalog pointer advances. Global publisher assets remain protected from tenant mutation.

## Offline regression boundary

The previous SSE test mocked the final ReAct answer but left perception, classification, memory, proactive guidance and background persistence paths active. The shared unit-test helper now stubs those external collaborators; response-event assertions remain unchanged. Separate suites continue to cover each collaborator’s behavior.

`tests/offline_network.py` blocks non-loopback HTTPX and Requests transports before proxy resolution, Python DNS/socket connections, and Google gRPC channel creation before credentials/RPC dispatch. It records attempts even if application code catches the exception and fails the test during teardown. MockTransport and loopback fixtures remain available. Guard self-tests deliberately prove OpenAI/proxy and Google/gRPC rejection without sending a request. CI runs this guard against the approved lifecycle, catalog and SSE contracts using synthetic keys.

## Validation

- Affected Marketplace, router, manifest, tenant and governance suite under the offline guard: **653 passed**.
- Approved tranche lifecycle tests: **26 passed**, including install/upgrade/rollback, idempotency, quota replacement, entitlement denial, connector denial, foreign-org denial, permissions preservation, forged guidance and concurrent version changes.
- Dedicated offline CI gate: **56 passed**, including the unchanged SSE assertions and transport guard self-tests, with zero accidental external network attempts.
- Complete final-SHA CI: pending at this checkpoint. See PR581 for exact-SHA results.
- Production acceptance: not run, per explicit no-deployment instruction.

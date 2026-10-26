# Qualified Prospecting Play — native integration contract

## What is shipped in this foundation PR

* Catalog entry for `qualified-prospecting`, visible through existing Plays catalog/API.
* Pure, fail-closed admission policy with unit tests.
* Provider and workflow integration contract below. No fake connector readiness.
* **No data ingestion execution, API credentials, CRM writes or email sends activated.**

## Target user journey

Discover companies → research websites → resolve named contacts → verify business
emails → confirm CASL basis/source rights → review → stage → approved CRM action.
Operators configure industry, country, buyer titles, quantity, spending limits,
schedule and destinations through the existing Play setup and workflow binding.

## Connector capability contracts (not yet implemented)

* `apollo.people.search`, `apollo.people.match`, `apollo.usage.read`
* `hunter.domain.search`, `hunter.email.find`, `hunter.email.verify`, `hunter.usage.read`
* `emailable.email.verify`, `emailable.usage.read`
* `snov.email.find`, `snov.email.verify` (disabled until entitlement)
* `millionverifier.email.verify` (disabled until entitlement)

Each is a native API-key connector package using existing scoped credential vault,
connector manifest, action schema and permission enforcement. Do not use Nango
OAuth for API-key-only integrations. Provider calls must be idempotent, rate-limited,
tenant-scoped and metered. Never log secret values or full contact PII.

## Canonical workflow steps (to bind, not a second engine)

1. `prospecting.discover`: permitted Geofabrik, Wikidata, open-data feeds
2. `prospecting.research`: bounded public-website fetch and deterministic parsing
3. `prospecting.enrich`: public names and Apollo contact lookup
4. `prospecting.verify`: cached checks, Hunter/Emailable credit-bounded waterfall
5. `prospecting.review`: evidence-based identity, consent and source-policy reviews
6. `prospecting.stage`: approved CRM destination write using PendingAction

Deduplicate by canonical organization domain and provider contact identifiers.
Keep source licence, source URL, timestamp, consent expiry/revocation and
per-tenant suppression across refreshes. Never infer consent from verification.

## Integration and release prerequisites

1. Migrate authoritative records to PostgreSQL with org_id, RLS and immutable evidence.
2. Implement connector packages, API-key vault onboarding and free-credit caps.
3. Bind canonical workflows and Prospecting Agent to shared IntelligenceRouter.
4. Build Play-specific UI status, review queue, provider allowance and results.
5. Test cross-tenant read/write leakage, contact mismatches, revoked consent,
   source prohibitions, credit exhaustion, out-of-order jobs, SSRF and rate limits.
6. Test 100+ real prospect candidates and legal review. Only then deploy with
   feature flags; enable CRM writes solely after canonical approval.
7. Sending remains a separate, opt-in governed Play action.

The Play catalog entry does **not** imply operational execution readiness.

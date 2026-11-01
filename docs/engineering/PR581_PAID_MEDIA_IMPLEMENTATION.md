# Approved Paid Media implementation

The user authorized full engineering of the previously approved complete Paid
Media inventory. This supersedes planning/staging restrictions for these seven
roles. PR581 stays open/draft; no merge, seed execution, deployment, live install,
campaign, publishing or spend is authorized by this implementation.

| Audited source role | Destination | Change | Live evidence prerequisite |
|---|---|---|---|
| PPC Campaign Strategist | ppc-campaign-strategist | New Marketing specialist | Google Ads |
| Search Query Analyst | seo-analyst | Existing-agent enrichment | Analytics + Google Ads |
| Paid Media Auditor | marketing-analyst | Existing-agent enrichment | HubSpot + Google Ads |
| Tracking & Measurement Specialist | marketing-ops-coordinator | Existing-agent enrichment | HubSpot + Analytics |
| Ad Creative Strategist | marketing-designer | Existing-agent enrichment | Canva |
| Programmatic & Display Buyer | programmatic-display-buyer | New Marketing specialist | Google Ads display only; no DSP connector |
| Paid Social Strategist | paid-social-strategist | New Marketing specialist | HubSpot audience context + supplied account evidence; no Meta/TikTok/LinkedIn Ads connector |

Duplicate resolution uses the existing catalog: analytics/audit, measurement ops,
creative and search-query roles enrich four existing agents. The remaining three
use the existing MARKETING persona with no default systems or capability/tool
grants. Source revision, hashes and MIT license are checked against the immutable
283-role source inventory. No upstream system prompt is imported.

These are explicit user-authorized agent surfaces, not placeholder products.
No new price, compliance badge, training claim, capability toggle or performance
claim is added. Existing catalog pricing defaults are reused. No live listing is
published by changing source. Marketing pack membership is unchanged.

Connector prerequisites are checked by canonical installation; notably enriched
SEO installs/upgrades now require Google Ads alongside Analytics. Installed
instances do not change automatically. A requirement is a readiness check, never
an OAuth scope, tool grant or spending authorization. Supported connector presence
does not imply a particular account's access, GTM/CAPI access, causal attribution,
DSP support or another advertising platform's availability.

Exact versioned references render the same curated bounded guidance in full and
compact/unified/voice prompts. All roles consume PR587's shared dialogue,
intelligence, memory and feedback. They add no brain, session store or execution
path. Reports/drafts are advisory; campaign creation, publishing, audience uploads,
negative-keyword uploads, billing and bid/budget/spend changes retain existing
catalog authority, tenant IAM, connector scopes, quotas and explicit approvals.

Canonical seeding now versions these changes using publication-before-install
integrity and optimistic pointer updates. Install/upgrade/rollback tests exercise
stable entity identity, immutable baseline snapshots, idempotency, cross-tenant
connectors/entitlements/visibility, unpublished snapshot denial (including force),
exact reference rejection and unchanged tool-grant counts. New agents receive zero
default grants. The separate six-role tranche tests remain in place.

A metrics-only Langfuse feedback adapter reads a tenant-scoped durable evaluation
receipt, validates it against the run and exports only keyed correlation, enum
channel/evaluator and bounded counts/duration. It requires the existing explicit
per-run permit and injected configured client. Submission is not durable remote
delivery. No automatic telemetry activation or provider SDK dependency is added.

Catalog cardinality assertions change from 23 to 26 agents (88 to 91 total) because
of the three authorized specialists. The ordinary seed-idempotency test now names
an unchanged asset rather than selecting index zero, which now has versioned
Paid Media enrichment. Its original insert/update assertions remain unchanged;
new versioned idempotency has its own filter-honoring lifecycle tests. No gate is
relaxed to hide the new path.

Current source/regression/CI evidence is recorded on the PR description. Deployed
acceptance and physical voice remain NOT_RUN until the authorized release stage.

# LinkedIn Sales Navigator / Marketing API — ADR (STA-62, STA-63)

## Status

**Accepted** — go with LinkedIn Marketing API profile enrichment where available; manual-field fallback otherwise.

## Context

Gravitre Sales Agent workflows need prospect enrichment (title, company, seniority) for outbound qualification. Two LinkedIn integration paths exist:

| Path | Access model | Profile / lead data | Typical customer |
|------|--------------|---------------------|------------------|
| **LinkedIn Marketing API** | OAuth 2.0 via LinkedIn Developer app; scoped to ad / lead-gen / matched audiences | Limited B2B enrichment via Lead Gen Forms, Matched Audiences, and organization endpoints — **not** full Sales Navigator search | Marketing ops with LinkedIn Campaign Manager |
| **Sales Navigator Partner Program** | Restricted ISV partnership; separate contracts and compliance review | Full SN search, lists, and CRM sync APIs | Enterprise with SN seats + legal approval |

## Decision

1. **Primary integration:** LinkedIn **Marketing API** for `linkedin.prospect.enrich` when the org connector has a valid OAuth access token with applicable scopes.
2. **Fallback:** When no token is configured, OAuth is incomplete, or the API returns 403/404, return a **structured stub** built from workflow input parameters (`email`, `first_name`, `last_name`, `company`, `title`, `linkedin_url`) so agents and workflows remain executable.
3. **Do not** implement Sales Navigator Partner APIs in Tier 3 without a signed partner agreement and dedicated compliance review.

## Rationale

- Marketing API is obtainable via standard LinkedIn Developer onboarding; SN Partner Program requires months-long legal/commercial gates.
- Most Gravitre customers already store partial lead data in CRM; stub enrichment preserves workflow continuity.
- Marketing API rate limits and ToS are published; SN scraping or unofficial APIs violate LinkedIn ToS and create platform risk.

## Rate limits (Marketing API)

LinkedIn applies **per-app** and **per-member** throttling. Documented guidance (subject to change on [LinkedIn Developer](https://learn.microsoft.com/en-us/linkedin/)):

- REST calls: commonly **~100 requests/day** for development tiers; production tiers vary by product.
- Lead Gen / Conversions APIs: burst limits with `429` + `Retry-After`.
- Gravitre connector enforces org-level rate limits via `enforce_rate_limit` on tool invoke.

**Mitigation:** cache enrichment per `(org_id, email)` in workflow parameters; prefer CRM-sourced fields before calling LinkedIn.

## Terms of Service / compliance

- Use only **official** LinkedIn APIs with customer-granted OAuth consent.
- Do not store LinkedIn member data beyond customer-configured retention; honor deletion requests.
- Do not combine LinkedIn data with third-party contact databases for resale (prohibited).
- Sales Navigator UI automation, scraping, or browser extensions are **out of scope** and non-compliant.

## Go / no-go

| Criterion | Marketing API | Sales Navigator Partner |
|-----------|---------------|-------------------------|
| Available without partnership | **Go** | No-go (Tier 3) |
| Supports agent `prospect.enrich` with token | **Go** (partial) | Go (full, later) |
| Supports no-token demo / stub path | **Go** | N/A |
| Enterprise SN list sync | No-go (Tier 3) | Future tier |

## Implementation

- `backend/app/connectors/linkedin.py` — `enrich_prospect()`; Marketing API when token present, else stub.
- Agent tool action: `linkedin.prospect.enrich`
- Scopes: `linkedin:prospects:read`, `linkedin:*`

## Consequences

- Enrichment quality without SN partnership is **best-effort**; product copy must set expectations.
- Customers needing full SN search should pursue LinkedIn partner track separately; Gravitre can add a partner connector later without changing the stub contract.

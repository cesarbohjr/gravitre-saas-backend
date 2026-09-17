# Domain → property binding (org profile + resolver)

**Status:** structural (local). Does not expand the F1 ActionSpec slice. Does not change WRITE governance or G8.  
**Date:** 2026-09-17

Audit §34 item 3: when several GA4 properties (or GSC sites) are visible on a connection, auto-select only if **exactly one** candidate matches this tenant’s website. Otherwise keep `ambiguous` / genuine clarification.

## Sources (tenant-scoped)

| Priority | Source | Notes |
|---|---|---|
| 1 | User message host (`gravitre.app`, `https://…`) | Same-org candidate list only |
| 2 | Conversation `business_identity` / `company_website` | Existing F1 context |
| 3 | `organizations.settings` website keys | Query `.eq("id", org_id)`; reject mismatched row `id` |
| 4 | Verified branding `customDomain` | Only if `customDomainVerified` |
| 5 | Same-org linked GSC `site_url` | `get_connector_by_type(..., org_id)` |
| 6 | Unique company `org_knowledge_nodes` website | Rows with other `org_id` dropped |

No new customer-facing Settings field, price, claim, or Enable toggle.

## Match rules

- Host equality, or candidate host is a subdomain of the org host.
- Else unique display-name token equal to the registrable left label (length ≥ 4). Non-unique labels stay unbound.
- Cross-tenant `org_id` / `tenant_id` on a candidate is never eligible.
- Website identity still does **not** compile into `property_id` via `BUSINESS_IDENTITY` — only resolver/preflight unique bind.

GA4 Admin `dataStreams.defaultUri` is fetched only after a miss, max 8 properties, and only when a host exists.

## Wiring

- `resolve_ga4_property` after multiple discovered properties
- GSC (and other) adapters after `ambiguous`
- `preflight_read_action` identity via `merge_business_identity`

## Verification

Local: `backend/tests/services/test_domain_property_binding.py` plus existing F1 matcher tests.

**NOT PROVEN live:** production multi-property GA4 with org website set. Classify production PASS only after a live preflight with `resolution_reason=tenant_domain_binding`.

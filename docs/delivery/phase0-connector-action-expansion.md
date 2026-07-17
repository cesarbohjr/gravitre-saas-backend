# Phase 0 -- Connector action expansion inventory

**Date:** 2026-07-15  
**Scope:** Phase 0 only (enumeration + ranked batch plan). No connector code changes.  
**Sources:** `backend/app/connectors/action_catalog/vendor_definitions.py` (`build_vendor`), `backend/app/marketplace/intelligence_packs/catalog.py`, `connector_category_templates.py`, `seed_catalog.py`, connector modules / `catalog_http/profiles.py`, `intelligence_packs/shared/auth_mode.py`.

---

## 1. Summary counts

| Metric | Count |
|--------|------:|
| `build_vendor` entries | 75 |
| Shipped (`shipped=True`) | 56 |
| Unshipped (`shipped=False`) | 19 |
| Total catalog actions | 650 |

### Actions by name verb (catalog scan)

| list | get | create | update | delete | search | other |
|-----:|----:|-------:|-------:|-------:|-------:|------:|
| 138 | 83 | 106 | 40 | 16 | 23 | 244 |

### Actions by kind

- **read:** 242  - **write:** 177  - **advanced:** 231

### Vendors by catalog `department`

| Department | Vendors |
|------------|--------:|
| operations | 35 |
| marketing | 16 |
| finance | 7 |
| sales | 7 |
| support | 5 |
| security | 2 |
| healthcare | 1 |
| legal | 1 |
| real_estate | 1 |

> **Note:** HR vendors (`workday`, `bamboohr`, `greenhouse`, `gusto`, `adp`) are catalogued under `department=operations`, not a separate `hr` key. Finance F3 vendors share `department=finance` with gravitree macro sources (`fred`, `sec_edgar`).

### Out-of-catalog intelligence sources

These appear in packs / auth_mode / templates but have **no** `build_vendor` entry:

- **`crunchbase`** -- CONTACT_PII + GOVERNANCE_STOP_LINE
- **`world_bank`** -- LOW_GOVERNANCE public aggregate -- expansion candidate
- **`oecd`** -- LOW_GOVERNANCE public aggregate -- expansion candidate
- **`opencorporates`** -- LICENSE_BLOCKED

---

## 2. Governance flags

### GOVERNANCE_LAST -- Finance F3 / HR H3

Exclude from Phase 1 action-expansion batches until **F3/H3 live-invoke reaches DONE** (not PARTIAL unlock tip). As of 2026-07-16 tip `cd056edf`: both packs are **PARTIAL** (`live_invoke_ok: false`).

| Cohort | Vendors | Pack / template |
|--------|---------|-----------------|
| Finance F3 | `quickbooks`, `xero`, `netsuite`, `plaid` | `finance-intelligence-pack` / `finance-intelligence-sources` |
| HR H3 | `workday`, `bamboohr`, `greenhouse`, `gusto` | `hr-talent-intelligence-pack` / `hr-talent-intelligence-sources` |
| HR-adjacent unshipped | `adp` | _(none)_ |

### CONTACT_PII -- catalog-ok, Memory/KG STA-312

| Vendor | Catalog | Activation | Memory/KG |
|--------|---------|------------|-----------|
| `pdl` | shipped `build_vendor` (4 read actions) | BYO_REQUIRED (allowed with tenant key) | STA-312 gated |
| `crunchbase` | **missing** from `build_vendor` | GOVERNANCE_STOP_LINE | STA-312 gated |

---

## 3. Known API version gaps (code vs catalog docs)

| Vendor | Catalog docs URL | Hardcoded / runtime API | Gap |
|--------|------------------|-------------------------|-----|
| `hubspot` | developers.hubspot.com/docs/api/overview | api.hubapi.com CRM **v3** + assoc/seq **v4** | Docs generic; code v3/v4 mix |
| `apollo` | apolloio.github.io/apollo-api-docs | api.apollo.io/**api/v1** | Pinned v1 |
| `ahrefs` | docs.ahrefs.com/.../introduction | api.ahrefs.com/**v3** | Docs generic; code v3 |
| `pdl` | docs.peopledatalabs.com | api.peopledatalabs.com/**v5** | v5 |
| `salesforce` | developer.salesforce.com/.../api_rest | {instance}/services/data/**v59.0** | Pinned v59.0 |
| `google_search_console` | webmaster-tools/**v1** docs | googleapis.com/webmasters/**v3** | Docs v1 vs path v3 |
| `linkedin` | LinkedIn Marketing docs | api.linkedin.com/**rest** (202405); profile still **/v2** | Profile vs module mismatch |
| `semrush` | developer.semrush.com/api/**v3**/analytics/... | legacy + analytics/**v1** + apis/**v4**/projects | Multi-version surface |
| `github` | docs.github.com/en/rest | api.github.com (no /vN path) | OK |
| `slack` | api.slack.com/methods | slack.com/api + OAuth **v2** | OK |
| `pipedrive` | developers.pipedrive.com/docs/api/**v1** | api.pipedrive.com/api/**v1** | Aligned |
| `clio` | docs.developers.clio.com | app.clio.com/api/**v4** | v4 |
| `quickbooks` | Intuit QBO docs | quickbooks.api.intuit.com/**v3** | v3; GOVERNANCE_LAST |
| `xero` | Xero accounting overview | api.xero.com/api.xro/**2.0** | Accounting API 2.0 |
| `confluence` | Atlassian Confluence REST **v2** | wiki/api/**v2** | Aligned |
| `jira` | Jira Cloud REST **v3** | (docs / Atlassian) | v3 |
| `fred` | fred.stlouisfed.org/docs/api/fred | api.stlouisfed.org/fred | OK |
| `nvd` | nvd.nist.gov/developers | services.nvd.nist.gov/rest/json | OK |
| `sec_edgar` | sec.gov EDGAR search page | efts.sec.gov/LATEST | Full-text search API |
| `crunchbase` | _(no build_vendor)_ | _(no module)_ | **v3->v4 NOT confirmed in repo** |
| `world_bank` | _(no build_vendor)_ | api.worldbank.org/**v2** | Out of catalog |
| `oecd` | _(no build_vendor)_ | sdmx.oecd.org/public/rest/data | Out of catalog |

### Crunchbase v3->v4 (Batch 1 candidate)

**Status: NOT CONFIRMED in this codebase.** There is no `crunchbase` `build_vendor`, no `*_api.py` client, and no `api.crunchbase.com` string. Only `CRUNCHBASE_API_KEY` / docs `CRUNCHBASE_BASE_URL` plus `GOVERNANCE_STOP_LINE`. Treat **Batch 1 as conditional**: confirm target API (expected industry v4) + lift activation gate + add catalog entry before any expansion work. Until then, skip to the next low-governance proven connector.

---

## 4. Intelligence pack / demo_systems / seed map

| Pack | demo_systems | connector_template | Workflow actions |
|------|--------------|--------------------|------------------|
| `marketing-intelligence-pack` | `google_search_console`, `google_analytics`, `hubspot` | `marketing-intelligence-sources` | `searchconsole.sites.list` |
| `revops-intelligence-pack` | `hubspot` | `revops-intelligence-sources` | `hubspot.pipelines.list` |
| `ai-search-intelligence-pack` | `ahrefs`, `finseo`, `ai_visibility_ui` | `ai-search-intelligence-sources` | `ahrefs.brand_radar.overview` |
| `finance-intelligence-pack` | `quickbooks`, `xero`, `netsuite`, `plaid` | `finance-intelligence-sources` | `quickbooks.companyinfo.get` |
| `hr-talent-intelligence-pack` | `workday`, `bamboohr`, `greenhouse`, `gusto` | `hr-talent-intelligence-sources` | `greenhouse.jobs.list` |
| `sales-intelligence-pack` | `hubspot` | `sales-intelligence-sources` | `hubspot.pipelines.list` |
| `prospecting-intelligence-pack` | `apollo`, `hubspot` | `prospecting-intelligence-sources` | `apollo.organizations.search`, `apollo.people.search`, `apollo.lists.create`, `hubspot.lists.create` |
| `support-intelligence-pack` | -- | `--(no template)` | -- |
| `customer-success-intelligence-pack` | `hubspot`, `zendesk` | `customer-success-intelligence-sources` | `hubspot.pipelines.list`, `hubspot.deals.list`, `zendesk.tickets.list` |
| `msp-intelligence-pack` | `nvd`, `cisa_kev` | `msp-intelligence-sources` | `nvd.cve.get`, `cisa_kev.feed.get` |
| `executive-intelligence-pack` | `fred`, `sec_edgar` | `executive-intelligence-sources` | `fred.series.get`, `sec_edgar.filings.search` |

**Seed catalog extras:** `hubspot`, `slack`, `apollo`, `ahrefs`, `pdl`, `salesforce`, Finance F3 cards, HR H3 cards appear in `seed_catalog.py` / `seed_catalog_expansion.py` beyond pack `demo_systems`.

---

## 5. Full vendor inventory (`build_vendor`)

Action verb counts are derived from the **last segment** of each action id (e.g. `contacts.search` -> search; `deals.update_stage` -> update). `other` covers verbs like `identify`, `track`, `enroll`, `enrich`, etc.

### 1. `salesforce` -- Salesforce

- **Shipped:** True
- **Department:** `sales`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/
- **Code / profile API base:** {instance}/services/data/v59.0 (DEFAULT_API_VERSION in salesforce.py)
- **Version / governance note:** Catalog docs generic REST; code pins v59.0
- **Action count:** 12
- **By kind:** read=4, write=5, advanced=3
- **By verb:** list=0, get=3, create=4, update=4, delete=0, search=1, other=0
- **Action ids:** `leads.get`, `leads.search`, `accounts.get`, `opportunities.get`, `leads.create`, `leads.update`, `accounts.create`, `opportunities.create`, `tasks.create`, `opportunities.update_stage`, `accounts.update`, `opportunities.update`
- **Pack / seed:** templates: revops-intelligence-sources; seed: seed_catalog agents (RevOps/Sales)

### 2. `hubspot` -- HubSpot

- **Shipped:** True
- **Department:** `sales`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://developers.hubspot.com/docs/api/overview
- **Code / profile API base:** https://api.hubapi.com -- CRM objects `/crm/v3/...`; associations `/crm/v4/...`; sequences `/automation/v4/...`
- **Version / governance note:** Catalog docs are overview-only; runtime is HubSpot CRM v3 + selective v4
- **Action count:** 22
- **By kind:** read=9, write=8, advanced=5
- **By verb:** list=2, get=3, create=5, update=3, delete=3, search=4, other=2
- **Action ids:** **read** (9): `contacts.get`, `contacts.search`, `deals.get`, `deals.search`, `deals.list`, `companies.search`, ... +3 more<br>**write** (8): `contacts.create`, `contacts.update`, `contacts.delete`, `deals.create`, `deals.update`, `deals.delete`, `notes.create`, `notes.delete`<br>**advanced** (5): `deals.update_stage`, `sequences.enroll`, `lists.add_contact`, `lists.create`, `tickets.create`
- **Pack / seed:** demo_systems: marketing-intelligence-pack, revops-intelligence-pack, sales-intelligence-pack, prospecting-intelligence-pack, customer-success-intelligence-pack; workflow/assignment refs: revops-intelligence-pack, sales-intelligence-pack, prospecting-intelligence-pack, customer-success-intelligence-pack; templates: sales-intelligence-sources, prospecting-intelligence-sources, customer-success-intelligence-sources, marketing-intelligence-sources, revops-intelligence-sources; seed: seed_catalog (+ expansion): agents/workflows/systems

### 3. `pipedrive` -- Pipedrive

- **Shipped:** True
- **Department:** `sales`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://developers.pipedrive.com/docs/api/v1
- **Code / profile API base:** https://api.pipedrive.com/api/v1
- **Version / governance note:** Matches docs URL (api/v1)
- **Action count:** 11
- **By kind:** read=6, write=4, advanced=1
- **By verb:** list=3, get=2, create=2, update=3, delete=0, search=1, other=0
- **Action ids:** `persons.search`, `persons.get`, `deals.list`, `deals.get`, `organizations.list`, `pipelines.list`, `persons.create`, `persons.update`, `deals.create`, `deals.update`, `deals.update_stage`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 4. `marketo` -- Marketo

- **Shipped:** True
- **Department:** `marketing`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://developers.marketo.com/rest-api/
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=1, get=1, create=1, update=1, delete=0, search=0, other=5
- **Action ids:** `leads.get`, `campaigns.list`, `programs.status`, `leads.update`, `leads.create`, `campaigns.schedule`, `lists.add_to_static_list`, `leads.merge`, `programs.members.add`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 5. `segment` -- Segment

- **Shipped:** True
- **Department:** `marketing`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://segment.com/docs/connections/sources/catalog/libraries/server/http-api/
- **Code / profile API base:** https://api.segmentapis.com
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=3, get=0, create=0, update=0, delete=0, search=0, other=6
- **Action ids:** `sources.list`, `destinations.list`, `trackingplans.list`, `identify`, `track`, `group`, `alias`, `page`, `batch`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 6. `google_analytics` -- Google Analytics

- **Shipped:** True
- **Department:** `marketing`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://developers.google.com/analytics/devguides/reporting/data/v1
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=0, create=2, update=0, delete=0, search=0, other=4
- **Action ids:** `properties.list`, `reports.run`, `metadata.list`, `audiences.create`, `conversions.create`, `reports.batch`, `realtime.run`, `funnels.run`
- **Pack / seed:** demo_systems: marketing-intelligence-pack; templates: marketing-intelligence-sources; seed: seed_catalog marketing agents

### 7. `google_search_console` -- Google Search Console

- **Shipped:** True
- **Department:** `marketing`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://developers.google.com/webmaster-tools/v1/api_reference_index
- **Code / profile API base:** https://www.googleapis.com/webmasters/v3 (google_search_console.py)
- **Version / governance note:** Catalog docs say webmaster-tools/v1; runtime uses Webmasters API v3 path
- **Action count:** 4
- **By kind:** read=3, write=0, advanced=1
- **By verb:** list=2, get=1, create=0, update=0, delete=0, search=0, other=1
- **Action ids:** `sites.list`, `searchAnalytics.query`, `sites.get`, `sitemaps.list`
- **Pack / seed:** demo_systems: marketing-intelligence-pack; workflow/assignment refs: marketing-intelligence-pack; templates: marketing-intelligence-sources

### 8. `mailchimp` -- Mailchimp

- **Shipped:** False
- **Department:** `marketing`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://mailchimp.com/developer/marketing/api/
- **Code / profile API base:** https://{dc}.api.mailchimp.com/3.0
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=2, get=1, create=1, update=0, delete=0, search=0, other=5
- **Action ids:** `audiences.list`, `members.get`, `campaigns.list`, `members.add`, `campaigns.create`, `tags.add`, `automations.trigger`, `segments.add_member`, `batch.subscribe`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 9. `mixpanel` -- Mixpanel

- **Shipped:** False
- **Department:** `marketing`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://developer.mixpanel.com/reference/overview
- **Code / profile API base:** https://mixpanel.com/api/2.0
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=0, create=1, update=0, delete=0, search=0, other=5
- **Action ids:** `events.query`, `funnels.list`, `cohorts.list`, `profiles.set`, `events.track`, `cohorts.export`, `annotations.create`, `engage.query`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 10. `constant_contact` -- Constant Contact

- **Shipped:** True
- **Department:** `marketing`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://developer.constantcontact.com/api_guide/server_flow.html
- **Code / profile API base:** https://api.cc.email/v3
- **Action count:** 12
- **By kind:** read=3, write=3, advanced=6
- **By verb:** list=4, get=1, create=2, update=1, delete=1, search=0, other=3
- **Action ids:** `contacts.list`, `contacts.get`, `campaigns.list`, `contacts.create`, `contacts.update`, `campaigns.create`, `lists.add_contacts`, `tags.apply`, `campaigns.schedule`, `contact_lists.list`, `segments.list`, `contacts.delete`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 11. `hootsuite` -- Hootsuite

- **Shipped:** False
- **Department:** `marketing`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://developer.hootsuite.com/docs/api-overview
- **Code / profile API base:** https://platform.hootsuite.com/v1
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=0, create=0, update=1, delete=0, search=0, other=5
- **Action ids:** `organizations.list`, `messages.list`, `analytics.summary`, `messages.schedule`, `messages.update`, `inbox.reply`, `approvals.submit`, `bulk.schedule`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 12. `semrush` -- SEMrush

- **Shipped:** True
- **Department:** `marketing`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://developer.semrush.com/api/v3/analytics/basic-docs/
- **Code / profile API base:** api.semrush.com/ + analytics/v1 + apis/v4/projects/v1 + management/v1
- **Version / governance note:** Catalog docs point at v3 analytics; code mixes legacy + v1/v4 endpoints
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=0, create=1, update=0, delete=0, search=0, other=5
- **Action ids:** `domain.overview`, `keywords.list`, `backlinks.list`, `projects.create`, `position_tracking.add`, `batch.domain`, `competitors.compare`, `exports.run`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 13. `ahrefs` -- Ahrefs

- **Shipped:** True
- **Department:** `marketing`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://docs.ahrefs.com/docs/api/reference/introduction
- **Code / profile API base:** https://api.ahrefs.com/v3 (ahrefs_api.py)
- **Version / governance note:** Docs URL is generic; code hardcodes Ahrefs API v3
- **Action count:** 12
- **By kind:** read=8, write=3, advanced=1
- **By verb:** list=4, get=0, create=1, update=0, delete=0, search=0, other=7
- **Action ids:** `backlinks.list`, `keywords.list`, `domain.rating`, `brand_radar.overview`, `brand_radar.prompts.list`, `projects.create`, `rank_tracker.add`, `brand_radar.prompts.track`, `competitors.compare`, `top_pages.list`, `brand_radar.competitors.compare`, `brand_radar.exports.run`
- **Pack / seed:** demo_systems: ai-search-intelligence-pack; workflow/assignment refs: ai-search-intelligence-pack; templates: ai-search-intelligence-sources; seed: seed_catalog connector card

### 14. `finseo` -- Finseo

- **Shipped:** True
- **Department:** `marketing`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://www.finseo.ai/developers/api
- **Code / profile API base:** https://api.finseo.ai/v1
- **Action count:** 6
- **By kind:** read=4, write=1, advanced=1
- **By verb:** list=2, get=0, create=0, update=0, delete=0, search=0, other=4
- **Action ids:** `projects.list`, `metrics.overview`, `prompts.list`, `prompts.track`, `competitors.compare`, `exports.run`
- **Pack / seed:** demo_systems: ai-search-intelligence-pack; templates: ai-search-intelligence-sources

### 15. `ai_visibility_ui` -- AI Visibility UI

- **Shipped:** True
- **Department:** `marketing`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://gravitre.app/docs/delivery/phase8-ai-search-research-spike
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 4
- **By kind:** read=2, write=1, advanced=1
- **By verb:** list=1, get=0, create=0, update=0, delete=0, search=0, other=3
- **Action ids:** `surfaces.list`, `mentions.check`, `prompts.batch`, `captures.export`
- **Pack / seed:** demo_systems: ai-search-intelligence-pack; templates: ai-search-intelligence-sources

### 16. `pdl` -- People Data Labs

- **Shipped:** True
- **Department:** `sales`
- **Category:** CRM / Sales
- **Catalog docs URL:** https://docs.peopledatalabs.com/
- **Code / profile API base:** https://api.peopledatalabs.com/v5 (pdl_api.py)
- **Version / governance note:** PDL v5; Memory/KG contact writes STA-312 gated
- **Action count:** 4
- **By kind:** read=4, write=0, advanced=0
- **By verb:** list=0, get=0, create=0, update=0, delete=0, search=0, other=4
- **Action ids:** `person.enrich`, `company.enrich`, `person.identify`, `person.prefetch`
- **Pack / seed:** seed: seed_catalog connector card (BYO)
- **Flags:** CONTACT_PII -- catalog-ok; Memory/KG STA-312

### 17. `stackadapt` -- StackAdapt

- **Shipped:** False
- **Department:** `marketing`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://docs.stackadapt.com/
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=1, get=1, create=1, update=1, delete=0, search=0, other=4
- **Action ids:** `campaigns.list`, `campaigns.get`, `stats.summary`, `campaigns.create`, `campaigns.update`, `audiences.sync`, `creatives.upload`, `reports.export`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 18. `linkedin` -- LinkedIn

- **Shipped:** True
- **Department:** `sales`
- **Category:** Sales / Prospecting
- **Catalog docs URL:** https://learn.microsoft.com/en-us/linkedin/marketing/
- **Code / profile API base:** https://api.linkedin.com/rest + Linkedin-Version: 202405 (linkedin.py); profile still lists api.linkedin.com/v2
- **Version / governance note:** Profile/catalog vs module mismatch: `/rest` (versioned) vs `/v2`
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=1, get=1, create=0, update=1, delete=0, search=0, other=5
- **Action ids:** `prospect.enrich`, `organizations.get`, `ads.accounts.list`, `leads.submit`, `audience.update`, `campaigns.optimize`, `conversions.track`, `batch.enrich`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 19. `apollo` -- Apollo

- **Shipped:** True
- **Department:** `sales`
- **Category:** Sales / Prospecting
- **Catalog docs URL:** https://apolloio.github.io/apollo-api-docs/
- **Code / profile API base:** https://api.apollo.io/api/v1 (apollo_api.py + catalog_http profile)
- **Version / governance note:** Stable v1; no v2 API path in code
- **Action count:** 13
- **By kind:** read=4, write=3, advanced=6
- **By verb:** list=1, get=1, create=3, update=1, delete=1, search=2, other=4
- **Action ids:** `people.search`, `organizations.search`, `contacts.get`, `lists.list`, `contacts.create`, `lists.create`, `sequences.add`, `enrichment.bulk`, `tasks.create`, `signals.subscribe`, `contacts.update`, `contacts.delete`, `sequences.remove`
- **Pack / seed:** demo_systems: prospecting-intelligence-pack; workflow/assignment refs: prospecting-intelligence-pack; templates: sales-intelligence-sources, prospecting-intelligence-sources; seed: seed_catalog connector card + prospecting pack

### 20. `clay` -- Clay

- **Shipped:** True
- **Department:** `sales`
- **Category:** Sales / Prospecting
- **Catalog docs URL:** https://university.clay.com/docs/using-clay-as-an-api
- **Code / profile API base:** https://api.clay.com
- **Action count:** 7
- **By kind:** read=4, write=2, advanced=1
- **By verb:** list=1, get=1, create=0, update=0, delete=0, search=0, other=5
- **Action ids:** `tables.list`, `people.enrich`, `companies.enrich`, `workflows.output.get`, `leads.push`, `enrichments.request`, `crm.sync`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 21. `engagebay` -- EngageBay

- **Shipped:** True
- **Department:** `marketing`
- **Category:** CRM / Marketing
- **Catalog docs URL:** https://developer.engagebay.com/
- **Code / profile API base:** https://app.engagebay.com/dev/api
- **Action count:** 6
- **By kind:** read=3, write=2, advanced=1
- **By verb:** list=1, get=1, create=2, update=1, delete=0, search=1, other=0
- **Action ids:** `contacts.search`, `contacts.get`, `deals.list`, `contacts.create`, `contacts.update`, `tasks.create`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 22. `stripe` -- Stripe

- **Shipped:** True
- **Department:** `finance`
- **Category:** Payments / Finance
- **Catalog docs URL:** https://docs.stripe.com/api
- **Code / profile API base:** https://api.stripe.com/v1
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=1, get=2, create=4, update=1, delete=0, search=0, other=1
- **Action ids:** `invoices.list`, `subscriptions.get`, `customers.get`, `customers.create`, `invoices.create`, `refunds.create`, `subscriptions.update`, `payment_intents.confirm`, `checkout.sessions.create`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 23. `quickbooks` -- QuickBooks

- **Shipped:** True
- **Department:** `finance`
- **Category:** Payments / Finance
- **Catalog docs URL:** https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/account
- **Code / profile API base:** https://quickbooks.api.intuit.com/v3/company/{realm_id}
- **Version / governance note:** GOVERNANCE_LAST until F3 live-invoke DONE
- **Action count:** 16
- **By kind:** read=8, write=3, advanced=5
- **By verb:** list=6, get=5, create=4, update=0, delete=0, search=1, other=0
- **Action ids:** `invoices.list`, `invoices.get`, `customers.list`, `customers.get`, `vendors.list`, `accounts.list`, `payments.list`, `companyinfo.get`, `invoices.create`, `customers.create`, `payments.create`, `customers.search`, `bills.list`, `bills.get`, `vendors.get`, `journalentries.create`
- **Pack / seed:** demo_systems: finance-intelligence-pack; workflow/assignment refs: finance-intelligence-pack; templates: finance-intelligence-sources; seed: seed_catalog finance connector card + CFO agent
- **Flags:** GOVERNANCE_LAST (Finance F3 -- exclude until live-invoke DONE)

### 24. `netsuite` -- NetSuite

- **Shipped:** True
- **Department:** `finance`
- **Category:** Payments / Finance
- **Catalog docs URL:** https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_1540391670.html
- **Code / profile API base:** {instance_url}/services/rest
- **Version / governance note:** GOVERNANCE_LAST until F3 live-invoke DONE
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=1, get=4, create=3, update=1, delete=0, search=0, other=0
- **Action ids:** `customers.get`, `invoices.list`, `salesorders.get`, `customers.update`, `journalentries.create`, `salesorders.create`, `items.get`, `invoices.get`, `fulfillment.create`
- **Pack / seed:** demo_systems: finance-intelligence-pack; templates: finance-intelligence-sources; seed: seed_catalog finance connector card
- **Flags:** GOVERNANCE_LAST (Finance F3 -- exclude until live-invoke DONE)

### 25. `xero` -- Xero

- **Shipped:** True
- **Department:** `finance`
- **Category:** Payments / Finance
- **Catalog docs URL:** https://developer.xero.com/documentation/api/accounting/overview
- **Code / profile API base:** https://api.xero.com/api.xro/2.0
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=3, get=0, create=3, update=0, delete=0, search=0, other=3
- **Action ids:** `contacts.list`, `invoices.list`, `accounts.list`, `invoices.create`, `contacts.create`, `payments.create`, `banktransactions.import`, `reports.profitloss`, `batch.invoices`
- **Pack / seed:** demo_systems: finance-intelligence-pack; templates: finance-intelligence-sources; seed: seed_catalog finance connector card
- **Flags:** GOVERNANCE_LAST (Finance F3 -- exclude until live-invoke DONE)

### 26. `clio` -- Clio

- **Shipped:** True
- **Department:** `legal`
- **Category:** Legal
- **Catalog docs URL:** https://docs.developers.clio.com/
- **Code / profile API base:** https://app.clio.com/api/v4
- **Action count:** 8
- **By kind:** read=3, write=4, advanced=1
- **By verb:** list=1, get=1, create=2, update=0, delete=0, search=2, other=2
- **Action ids:** `contacts.search`, `contacts.get`, `matters.search`, `conflict.checklist`, `intake.tasks`, `matters.create`, `tasks.create`, `calendar_entries.list`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 27. `real_estate` -- Real Estate

- **Shipped:** True
- **Department:** `real_estate`
- **Category:** Real Estate
- **Catalog docs URL:** https://gravitre.app/docs/integration/real-estate-vertical-pack
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 4
- **By kind:** read=0, write=3, advanced=1
- **By verb:** list=0, get=0, create=0, update=0, delete=0, search=0, other=4
- **Action ids:** `mls.note`, `handoff.brief`, `listing.publish`, `mls.sync`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 28. `plaid` -- Plaid

- **Shipped:** True
- **Department:** `finance`
- **Category:** Payments / Finance
- **Catalog docs URL:** https://plaid.com/docs/api/
- **Code / profile API base:** https://production.plaid.com
- **Version / governance note:** GOVERNANCE_LAST until F3 live-invoke DONE
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=1, get=3, create=1, update=0, delete=0, search=0, other=3
- **Action ids:** `accounts.get`, `transactions.list`, `balances.get`, `link.token.create`, `public_token.exchange`, `transactions.sync`, `identity.get`, `investments.holdings`
- **Pack / seed:** demo_systems: finance-intelligence-pack; templates: finance-intelligence-sources; seed: seed_catalog finance connector card
- **Flags:** GOVERNANCE_LAST (Finance F3 -- exclude until live-invoke DONE)

### 29. `slack` -- Slack

- **Shipped:** True
- **Department:** `operations`
- **Category:** Communication
- **Catalog docs URL:** https://api.slack.com/methods
- **Code / profile API base:** https://slack.com/api (Web API methods; OAuth v2 authorize/token)
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=2, get=0, create=1, update=1, delete=0, search=0, other=5
- **Action ids:** `conversations.list`, `conversations.history`, `users.list`, `post_message`, `conversations.create`, `chat.update`, `files.upload`, `reactions.add`, `workflows.trigger`
- **Pack / seed:** seed: seed_catalog (+ expansion): agents/workflows/systems

### 30. `microsoft_teams` -- Microsoft Teams

- **Shipped:** False
- **Department:** `operations`
- **Category:** Communication
- **Catalog docs URL:** https://learn.microsoft.com/en-us/graph/api/resources/teams-api-overview
- **Code / profile API base:** https://graph.microsoft.com/v1.0
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=3, get=0, create=2, update=0, delete=0, search=0, other=3
- **Action ids:** `teams.list`, `channels.list`, `messages.list`, `messages.send`, `meetings.create`, `tabs.create`, `members.add`, `presence.set`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 31. `microsoft365` -- Microsoft 365

- **Shipped:** True
- **Department:** `operations`
- **Category:** Communication
- **Catalog docs URL:** https://learn.microsoft.com/en-us/graph/api/overview
- **Code / profile API base:** https://graph.microsoft.com/v1.0 (implied Graph)
- **Action count:** 22
- **By kind:** read=6, write=5, advanced=11
- **By verb:** list=8, get=1, create=3, update=1, delete=1, search=0, other=8
- **Action ids:** **read** (6): `users.get`, `mail.messages.list`, `calendar.events.list`, `teams.list`, `teams.channels.list`, `teams.messages.list`<br>**write** (5): `mail.send`, `calendar.events.create`, `files.upload`, `teams.messages.send`, `teams.meetings.create`<br>**advanced** (11): `excel.workbook.update`, `teams.notify`, `batch.mail`, `teams.tabs.create`, `teams.members.add`, `teams.presence.set`, ... +5 more
- **Pack / seed:** _(none in intelligence packs / templates)_

### 32. `gmail` -- Gmail

- **Shipped:** True
- **Department:** `operations`
- **Category:** Communication
- **Catalog docs URL:** https://developers.google.com/gmail/api/reference/rest
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=2, get=1, create=3, update=0, delete=0, search=0, other=3
- **Action ids:** `messages.list`, `messages.get`, `labels.list`, `messages.send`, `drafts.create`, `labels.create`, `threads.modify`, `messages.batch`, `watch.create`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 33. `google_calendar` -- Google Calendar

- **Shipped:** True
- **Department:** `operations`
- **Category:** Communication
- **Catalog docs URL:** https://developers.google.com/calendar/api/v3/reference
- **Code / profile API base:** Calendar API v3 (docs)
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=3, get=0, create=1, update=1, delete=1, search=0, other=3
- **Action ids:** `freebusy`, `events.list`, `calendars.list`, `events.create`, `events.update`, `events.delete`, `events.quick_add`, `acl.list`, `batch.events`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 34. `outlook` -- Outlook

- **Shipped:** False
- **Department:** `operations`
- **Category:** Communication
- **Catalog docs URL:** https://learn.microsoft.com/en-us/graph/api/resources/mail-api-overview
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=1, create=1, update=0, delete=0, search=0, other=4
- **Action ids:** `messages.list`, `messages.get`, `folders.list`, `messages.send`, `messages.reply`, `rules.create`, `categories.apply`, `batch.send`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 35. `twilio` -- Twilio

- **Shipped:** False
- **Department:** `operations`
- **Category:** Communication
- **Catalog docs URL:** https://www.twilio.com/docs/usage/api
- **Code / profile API base:** https://api.twilio.com/2010-04-01
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=1, create=3, update=0, delete=0, search=0, other=2
- **Action ids:** `messages.list`, `calls.list`, `accounts.get`, `messages.create`, `calls.create`, `verify.check`, `conversations.create`, `studio.flows.execute`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 36. `sendgrid` -- SendGrid

- **Shipped:** False
- **Department:** `operations`
- **Category:** Communication
- **Catalog docs URL:** https://docs.sendgrid.com/api-reference
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=1, create=0, update=0, delete=0, search=0, other=5
- **Action ids:** `messages.list`, `templates.list`, `stats.get`, `mail.send`, `contacts.upsert`, `campaigns.schedule`, `suppressions.add`, `batch.send`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 37. `email` -- Email

- **Shipped:** True
- **Department:** `operations`
- **Category:** Communication
- **Catalog docs URL:** https://datatracker.ietf.org/doc/html/rfc5321
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 5
- **By kind:** read=2, write=1, advanced=2
- **By verb:** list=0, get=0, create=0, update=0, delete=0, search=0, other=5
- **Action ids:** `messages.queue`, `delivery.status`, `send`, `send.template`, `batch.send`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 38. `pagerduty` -- PagerDuty

- **Shipped:** True
- **Department:** `support`
- **Category:** DevOps / Incidents
- **Catalog docs URL:** https://developer.pagerduty.com/api-reference/
- **Code / profile API base:** https://api.pagerduty.com
- **Action count:** 10
- **By kind:** read=4, write=3, advanced=3
- **By verb:** list=4, get=1, create=0, update=0, delete=0, search=0, other=5
- **Action ids:** `incidents.list`, `incidents.get`, `services.list`, `oncalls.list`, `incidents.acknowledge`, `incidents.resolve`, `incidents.add_note`, `incidents.escalate`, `incidents.reassign`, `incidents.notes.list`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 39. `github` -- GitHub

- **Shipped:** True
- **Department:** `operations`
- **Category:** DevOps / Incidents
- **Catalog docs URL:** https://docs.github.com/en/rest
- **Code / profile API base:** https://api.github.com (REST; no /v3 path prefix -- GitHub REST is versioned via Accept header)
- **Action count:** 12
- **By kind:** read=3, write=3, advanced=6
- **By verb:** list=2, get=3, create=2, update=0, delete=0, search=0, other=5
- **Action ids:** `pulls.list`, `issues.get`, `repos.get`, `issues.create`, `issues.comment`, `pulls.request_reviewer`, `actions.dispatch`, `pulls.merge`, `releases.create`, `issues.list`, `pulls.get`, `pulls.close`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 40. `notion` -- Notion

- **Shipped:** True
- **Department:** `operations`
- **Category:** Operations / Workflow
- **Catalog docs URL:** https://developers.notion.com/reference/intro
- **Code / profile API base:** https://api.notion.com/v1 + Notion-Version 2022-06-28
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=1, get=1, create=3, update=1, delete=0, search=1, other=2
- **Action ids:** `pages.get`, `databases.query`, `users.list`, `pages.create`, `pages.update`, `blocks.append`, `databases.create`, `search`, `comments.create`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 41. `confluence` -- Confluence

- **Shipped:** True
- **Department:** `operations`
- **Category:** Operations / Workflow
- **Catalog docs URL:** https://developer.atlassian.com/cloud/confluence/rest/v2/intro/
- **Code / profile API base:** https://api.atlassian.com/ex/confluence/{cloud_id}/wiki/api/v2
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=1, get=1, create=1, update=1, delete=0, search=1, other=4
- **Action ids:** `pages.get`, `spaces.list`, `pages.search`, `pages.create`, `pages.update`, `labels.add`, `attachments.upload`, `pages.move`, `export.pdf`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 42. `jira` -- Jira

- **Shipped:** True
- **Department:** `operations`
- **Category:** Operations / Workflow
- **Catalog docs URL:** https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/
- **Code / profile API base:** Atlassian Cloud REST v3 (docs)
- **Action count:** 10
- **By kind:** read=4, write=3, advanced=3
- **By verb:** list=2, get=1, create=1, update=1, delete=0, search=2, other=3
- **Action ids:** `issues.get`, `issues.search`, `projects.list`, `users.search`, `issues.create`, `issues.update`, `issues.comment`, `issues.transition`, `issues.assign`, `issues.transitions.list`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 43. `airtable` -- Airtable

- **Shipped:** False
- **Department:** `operations`
- **Category:** Operations / Workflow
- **Catalog docs URL:** https://airtable.com/developers/web/api/introduction
- **Code / profile API base:** https://api.airtable.com/v0
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=1, create=2, update=1, delete=1, search=0, other=1
- **Action ids:** `bases.list`, `records.list`, `records.get`, `records.create`, `records.update`, `records.delete`, `webhooks.create`, `batch.records`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 44. `asana` -- Asana

- **Shipped:** True
- **Department:** `operations`
- **Category:** Operations / Workflow
- **Catalog docs URL:** https://developers.asana.com/docs
- **Code / profile API base:** https://app.asana.com/api/1.0
- **Action count:** 12
- **By kind:** read=3, write=3, advanced=6
- **By verb:** list=3, get=1, create=2, update=1, delete=1, search=1, other=3
- **Action ids:** `tasks.get`, `projects.list`, `users.list`, `tasks.create`, `tasks.update`, `stories.create`, `tasks.add_project`, `sections.move`, `batch.tasks`, `tasks.delete`, `workspaces.list`, `tasks.search`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 45. `monday` -- Monday.com

- **Shipped:** True
- **Department:** `operations`
- **Category:** Operations / Workflow
- **Catalog docs URL:** https://developer.monday.com/api-reference/docs
- **Code / profile API base:** https://api.monday.com/v2
- **Action count:** 11
- **By kind:** read=3, write=2, advanced=6
- **By verb:** list=3, get=2, create=2, update=1, delete=1, search=0, other=2
- **Action ids:** `boards.list`, `items.get`, `users.list`, `items.create`, `items.update`, `automations.trigger`, `updates.create`, `batch.items`, `items.delete`, `boards.get`, `workspaces.list`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 46. `clickup` -- ClickUp

- **Shipped:** True
- **Department:** `operations`
- **Category:** Operations / Workflow
- **Catalog docs URL:** https://clickup.com/api
- **Code / profile API base:** https://api.clickup.com/api/v2
- **Action count:** 12
- **By kind:** read=3, write=3, advanced=6
- **By verb:** list=2, get=2, create=4, update=2, delete=1, search=0, other=1
- **Action ids:** `tasks.get`, `lists.get`, `spaces.list`, `tasks.create`, `tasks.update`, `comments.create`, `time_entries.create`, `goals.update`, `webhooks.create`, `tasks.delete`, `tasks.bulk_update`, `members.list`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 47. `zapier` -- Zapier

- **Shipped:** False
- **Department:** `operations`
- **Category:** Operations / Workflow
- **Catalog docs URL:** https://platform.zapier.com/docs
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=3, get=0, create=0, update=0, delete=0, search=0, other=5
- **Action ids:** `zaps.list`, `actions.list`, `runs.list`, `zaps.enable`, `hooks.trigger`, `tables.rows.upsert`, `batch.trigger`, `interfaces.submit`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 48. `n8n` -- n8n

- **Shipped:** False
- **Department:** `operations`
- **Category:** Operations / Workflow
- **Catalog docs URL:** https://docs.n8n.io/api/
- **Code / profile API base:** {instance_url}/api/v1
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=3, get=0, create=1, update=0, delete=0, search=0, other=4
- **Action ids:** `workflows.list`, `executions.list`, `credentials.list`, `workflows.create`, `workflows.activate`, `executions.retry`, `webhooks.trigger`, `batch.executions`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 49. `motion` -- Motion

- **Shipped:** False
- **Department:** `operations`
- **Category:** Operations / Workflow
- **Catalog docs URL:** https://docs.usemotion.com/
- **Code / profile API base:** https://api.usemotion.com/v1
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=1, create=1, update=1, delete=0, search=0, other=3
- **Action ids:** `tasks.list`, `projects.list`, `schedules.get`, `tasks.create`, `tasks.update`, `calendar.optimize`, `batch.reschedule`, `focus.block`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 50. `odoo` -- Odoo

- **Shipped:** True
- **Department:** `operations`
- **Category:** Operations / Workflow
- **Catalog docs URL:** https://www.odoo.com/documentation/17.0/developer/reference/external_api.html
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 12
- **By kind:** read=3, write=3, advanced=6
- **By verb:** list=2, get=1, create=4, update=1, delete=0, search=0, other=4
- **Action ids:** `partners.get`, `sales.orders.list`, `inventory.products.list`, `partners.create`, `sales.orders.create`, `invoices.create`, `manufacturing.orders.create`, `crm.leads.convert`, `batch.partners`, `partners.update`, `sales.orders.confirm`, `invoices.post`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 51. `zendesk` -- Zendesk

- **Shipped:** True
- **Department:** `support`
- **Category:** Customer Support
- **Catalog docs URL:** https://developer.zendesk.com/api-reference/
- **Code / profile API base:** https://{subdomain}.zendesk.com/api/v2
- **Action count:** 10
- **By kind:** read=3, write=4, advanced=3
- **By verb:** list=1, get=2, create=2, update=1, delete=0, search=0, other=4
- **Action ids:** `tickets.get`, `tickets.list`, `users.get`, `tickets.create`, `tickets.update`, `tickets.close`, `tickets.add_tags`, `tickets.merge`, `macros.apply`, `side_conversations.create`
- **Pack / seed:** demo_systems: customer-success-intelligence-pack; workflow/assignment refs: customer-success-intelligence-pack; templates: customer-success-intelligence-sources

### 52. `intercom` -- Intercom

- **Shipped:** True
- **Department:** `support`
- **Category:** Customer Support
- **Catalog docs URL:** https://developers.intercom.com/docs/references/rest-api/api.intercom.io/
- **Code / profile API base:** https://api.intercom.io
- **Action count:** 12
- **By kind:** read=3, write=3, advanced=6
- **By verb:** list=3, get=1, create=3, update=0, delete=1, search=1, other=3
- **Action ids:** `contacts.get`, `conversations.list`, `tickets.list`, `contacts.create`, `conversations.reply`, `tickets.create`, `tags.apply`, `series.trigger`, `notes.create`, `contacts.search`, `companies.list`, `contacts.delete`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 53. `freshdesk` -- Freshdesk

- **Shipped:** False
- **Department:** `support`
- **Category:** Customer Support
- **Catalog docs URL:** https://developers.freshdesk.com/api/
- **Code / profile API base:** https://{domain}.freshdesk.com/api/v2
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=1, get=2, create=2, update=1, delete=0, search=0, other=3
- **Action ids:** `tickets.get`, `tickets.list`, `contacts.get`, `tickets.create`, `tickets.update`, `notes.create`, `tickets.merge`, `automations.trigger`, `satisfaction.send`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 54. `gorgias` -- Gorgias

- **Shipped:** False
- **Department:** `support`
- **Category:** Customer Support
- **Catalog docs URL:** https://developers.gorgias.com/reference/introduction
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=1, get=2, create=1, update=0, delete=0, search=0, other=5
- **Action ids:** `tickets.get`, `tickets.list`, `customers.get`, `tickets.create`, `tickets.reply`, `macros.apply`, `rules.trigger`, `tags.apply`, `satisfaction.request`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 55. `workday` -- Workday

- **Shipped:** True
- **Department:** `operations`
- **Category:** HR / People
- **Catalog docs URL:** https://community.workday.com/sites/default/files/file-hosting/restapi/index.html
- **Code / profile API base:** {instance_url}
- **Version / governance note:** GOVERNANCE_LAST until H3 live-invoke DONE
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=2, create=0, update=1, delete=0, search=0, other=3
- **Action ids:** `workers.get`, `orgunits.list`, `positions.list`, `timeoff.request`, `jobs.update`, `timeoff.balance.get`, `learning.enroll`, `batch.workers.export`
- **Pack / seed:** demo_systems: hr-talent-intelligence-pack; templates: hr-talent-intelligence-sources; seed: seed_catalog HR connector card
- **Flags:** GOVERNANCE_LAST (HR H3 -- exclude until live-invoke DONE)

### 56. `bamboohr` -- BambooHR

- **Shipped:** True
- **Department:** `operations`
- **Category:** HR / People
- **Catalog docs URL:** https://documentation.bamboohr.com/reference
- **Code / profile API base:** https://api.bamboohr.com/api/gateway.php/{subdomain}/v1
- **Version / governance note:** GOVERNANCE_LAST until H3 live-invoke DONE
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=1, create=3, update=0, delete=0, search=0, other=2
- **Action ids:** `employees.get`, `employees.list`, `timeoff.requests.list`, `employees.create`, `timeoff.requests.create`, `onboarding.tasks.assign`, `reports.run`, `webhooks.create`
- **Pack / seed:** demo_systems: hr-talent-intelligence-pack; templates: hr-talent-intelligence-sources; seed: seed_catalog HR connector card
- **Flags:** GOVERNANCE_LAST (HR H3 -- exclude until live-invoke DONE)

### 57. `greenhouse` -- Greenhouse

- **Shipped:** True
- **Department:** `operations`
- **Category:** HR / People
- **Catalog docs URL:** https://developers.greenhouse.io/harvest.html
- **Code / profile API base:** https://harvest.greenhouse.io/v1
- **Version / governance note:** GOVERNANCE_LAST until H3 live-invoke DONE
- **Action count:** 5
- **By kind:** read=3, write=1, advanced=1
- **By verb:** list=2, get=1, create=2, update=0, delete=0, search=0, other=0
- **Action ids:** `candidates.get`, `applications.list`, `jobs.list`, `candidates.create`, `offers.create`
- **Pack / seed:** demo_systems: hr-talent-intelligence-pack; workflow/assignment refs: hr-talent-intelligence-pack; templates: hr-talent-intelligence-sources; seed: seed_catalog HR connector card
- **Flags:** GOVERNANCE_LAST (HR H3 -- exclude until live-invoke DONE)

### 58. `gusto` -- Gusto

- **Shipped:** True
- **Department:** `operations`
- **Category:** HR / People
- **Catalog docs URL:** https://docs.gusto.com/app-integrations/reference
- **Code / profile API base:** https://api.gusto.com/v1
- **Version / governance note:** GOVERNANCE_LAST until H3 live-invoke DONE
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=1, get=2, create=1, update=0, delete=0, search=0, other=4
- **Action ids:** `employees.get`, `payrolls.list`, `companies.get`, `employees.create`, `payrolls.run`, `benefits.enroll`, `contractors.pay`, `reports.generate`
- **Pack / seed:** demo_systems: hr-talent-intelligence-pack; templates: hr-talent-intelligence-sources; seed: seed_catalog HR connector card
- **Flags:** GOVERNANCE_LAST (HR H3 -- exclude until live-invoke DONE)

### 59. `adp` -- ADP

- **Shipped:** False
- **Department:** `operations`
- **Category:** HR / People
- **Catalog docs URL:** https://developers.adp.com/
- **Code / profile API base:** https://api.adp.com
- **Version / governance note:** GOVERNANCE_LAST (HR-adjacent; unshipped)
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=1, create=0, update=1, delete=0, search=0, other=4
- **Action ids:** `workers.get`, `paystatements.list`, `events.list`, `timecards.submit`, `profile.update`, `payroll.preview`, `benefits.elect`, `batch.workers.sync`
- **Pack / seed:** _(none in intelligence packs / templates)_
- **Flags:** GOVERNANCE_LAST (HR-adjacent)

### 60. `aws_s3` -- AWS S3

- **Shipped:** False
- **Department:** `operations`
- **Category:** Storage / Dev / Infra
- **Catalog docs URL:** https://docs.aws.amazon.com/AmazonS3/latest/API/Welcome.html
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=1, create=0, update=0, delete=2, search=0, other=3
- **Action ids:** `buckets.list`, `objects.list`, `objects.head`, `objects.put`, `objects.delete`, `presigned.get`, `multipart.upload`, `batch.delete`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 61. `postgresql` -- PostgreSQL

- **Shipped:** True
- **Department:** `operations`
- **Category:** Storage / Dev / Infra
- **Catalog docs URL:** https://www.postgresql.org/docs/current/sql.html
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=0, create=0, update=1, delete=0, search=0, other=5
- **Action ids:** `query.select`, `tables.list`, `schemas.list`, `query.insert`, `query.update`, `query.explain`, `batch.upsert`, `migrations.apply`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 62. `mongodb` -- MongoDB

- **Shipped:** False
- **Department:** `operations`
- **Category:** Storage / Dev / Infra
- **Catalog docs URL:** https://www.mongodb.com/docs/manual/reference/command/
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=0, create=0, update=1, delete=0, search=0, other=5
- **Action ids:** `collections.list`, `documents.find`, `indexes.list`, `documents.insert`, `documents.update`, `aggregation.run`, `change_streams.watch`, `batch.bulk_write`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 63. `snowflake` -- Snowflake

- **Shipped:** False
- **Department:** `operations`
- **Category:** Storage / Dev / Infra
- **Catalog docs URL:** https://docs.snowflake.com/en/developer-guide/sql-api/index
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=1, get=0, create=0, update=0, delete=0, search=0, other=7
- **Action ids:** `query.execute`, `warehouses.list`, `tables.describe`, `query.insert`, `stages.put`, `tasks.run`, `pipes.refresh`, `batch.copy`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 64. `google_drive` -- Google Drive

- **Shipped:** True
- **Department:** `operations`
- **Category:** Storage / Dev / Infra
- **Catalog docs URL:** https://developers.google.com/drive/api/reference/rest/v3
- **Code / profile API base:** Drive REST v3 (docs)
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=3, get=1, create=2, update=1, delete=0, search=0, other=2
- **Action ids:** `files.list`, `files.get`, `permissions.list`, `files.create`, `files.update`, `permissions.create`, `files.export`, `changes.list`, `batch.permissions`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 65. `google_docs` -- Google Docs

- **Shipped:** True
- **Department:** `operations`
- **Category:** Storage / Dev / Infra
- **Catalog docs URL:** https://developers.google.com/docs/api/reference/rest
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 7
- **By kind:** read=2, write=2, advanced=3
- **By verb:** list=0, get=1, create=1, update=0, delete=0, search=0, other=5
- **Action ids:** `documents.get`, `documents.batch_get`, `documents.create`, `documents.batch_update`, `documents.replace_text`, `documents.insert_table`, `export.pdf`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 66. `google_sheets` -- Google Sheets

- **Shipped:** True
- **Department:** `operations`
- **Category:** Storage / Dev / Infra
- **Catalog docs URL:** https://developers.google.com/sheets/api/reference/rest
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 9
- **By kind:** read=3, write=3, advanced=3
- **By verb:** list=0, get=2, create=2, update=1, delete=0, search=0, other=4
- **Action ids:** `spreadsheets.get`, `values.get`, `values.batch_get`, `values.update`, `values.append`, `spreadsheets.create`, `values.batch_update`, `charts.add`, `pivot.create`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 67. `absorb_lms` -- Absorb LMS

- **Shipped:** False
- **Department:** `operations`
- **Category:** Learning / Creative
- **Catalog docs URL:** https://docs.absorblms.com/
- **Code / profile API base:** https://{domain}.myabsorb.com/api/rest/v2
- **Action count:** 8
- **By kind:** read=3, write=2, advanced=3
- **By verb:** list=2, get=1, create=2, update=0, delete=0, search=0, other=3
- **Action ids:** `courses.list`, `enrollments.list`, `users.get`, `enrollments.create`, `courses.create`, `certificates.issue`, `reports.completion`, `batch.enroll`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 68. `canva` -- Canva

- **Shipped:** True
- **Department:** `marketing`
- **Category:** Learning / Creative
- **Catalog docs URL:** https://www.canva.dev/docs/connect/
- **Code / profile API base:** https://api.canva.com/rest/v1
- **Action count:** 11
- **By kind:** read=3, write=2, advanced=6
- **By verb:** list=3, get=3, create=3, update=0, delete=1, search=0, other=1
- **Action ids:** `designs.list`, `designs.get`, `folders.list`, `designs.create`, `exports.create`, `autofill.create`, `brand.templates.list`, `batch.exports`, `exports.get`, `brand.templates.get`, `designs.delete`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 69. `figma` -- Figma

- **Shipped:** True
- **Department:** `marketing`
- **Category:** Learning / Creative
- **Catalog docs URL:** https://developers.figma.com/docs/rest-api/
- **Code / profile API base:** https://api.figma.com/v1
- **Action count:** 11
- **By kind:** read=3, write=2, advanced=6
- **By verb:** list=4, get=1, create=2, update=0, delete=1, search=0, other=3
- **Action ids:** `files.get`, `files.meta`, `projects.list`, `comments.create`, `dev_resources.create`, `projects.files.list`, `comments.list`, `batch.images.export`, `comments.delete`, `files.versions.list`, `users.me`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 70. `fhir` -- FHIR

- **Shipped:** True
- **Department:** `healthcare`
- **Category:** Healthcare
- **Catalog docs URL:** https://www.hl7.org/fhir/
- **Code / profile API base:** sandbox default https://hapi.fhir.org/baseR4
- **Action count:** 5
- **By kind:** read=3, write=1, advanced=1
- **By verb:** list=0, get=1, create=0, update=0, delete=0, search=2, other=2
- **Action ids:** `patients.get`, `patients.search`, `appointments.search`, `prior_auth.checklist`, `coverage.eligibility`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 71. `webhook` -- Webhook

- **Shipped:** True
- **Department:** `operations`
- **Category:** Integration
- **Catalog docs URL:** https://docs.gravitre.ai/connectors/webhook
- **Code / profile API base:** _(no dedicated module hit; may use generic HTTP bridge or stub)_
- **Action count:** 3
- **By kind:** read=1, write=1, advanced=1
- **By verb:** list=0, get=1, create=0, update=0, delete=0, search=0, other=2
- **Action ids:** `connectors.get`, `post`, `post.replay`
- **Pack / seed:** _(none in intelligence packs / templates)_

### 72. `fred` -- FRED

- **Shipped:** True
- **Department:** `finance`
- **Category:** Economic Data
- **Catalog docs URL:** https://fred.stlouisfed.org/docs/api/fred/
- **Code / profile API base:** https://api.stlouisfed.org/fred (executive/sources.py)
- **Version / governance note:** Catalog department=finance but auth gravitree_managed -- not Finance F3
- **Action count:** 3
- **By kind:** read=2, write=0, advanced=1
- **By verb:** list=0, get=2, create=0, update=0, delete=0, search=1, other=0
- **Action ids:** `series.get`, `series.search`, `series.observations.get`
- **Pack / seed:** demo_systems: executive-intelligence-pack; workflow/assignment refs: executive-intelligence-pack; templates: executive-intelligence-sources
- **Flags:** Note: catalog dept=finance but NOT Finance F3 (gravitree macro)

### 73. `nvd` -- NVD

- **Shipped:** True
- **Department:** `security`
- **Category:** Security
- **Catalog docs URL:** https://nvd.nist.gov/developers
- **Code / profile API base:** https://services.nvd.nist.gov/rest/json
- **Action count:** 3
- **By kind:** read=2, write=0, advanced=1
- **By verb:** list=0, get=1, create=0, update=0, delete=0, search=1, other=1
- **Action ids:** `cve.get`, `cve.search`, `cve.recent`
- **Pack / seed:** demo_systems: msp-intelligence-pack; workflow/assignment refs: msp-intelligence-pack; templates: msp-intelligence-sources

### 74. `cisa_kev` -- CISA KEV

- **Shipped:** True
- **Department:** `security`
- **Category:** Security
- **Catalog docs URL:** https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- **Code / profile API base:** https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
- **Action count:** 3
- **By kind:** read=2, write=0, advanced=1
- **By verb:** list=0, get=1, create=0, update=0, delete=0, search=0, other=2
- **Action ids:** `feed.get`, `cve.lookup`, `feed.diff`
- **Pack / seed:** demo_systems: msp-intelligence-pack; workflow/assignment refs: msp-intelligence-pack; templates: msp-intelligence-sources

### 75. `sec_edgar` -- SEC EDGAR

- **Shipped:** True
- **Department:** `finance`
- **Category:** Finance
- **Catalog docs URL:** https://www.sec.gov/edgar/searchedgar/companysearch
- **Code / profile API base:** https://efts.sec.gov/LATEST (SEC_BASE_URL default)
- **Version / governance note:** Requires SEC_USER_AGENT
- **Action count:** 3
- **By kind:** read=2, write=0, advanced=1
- **By verb:** list=0, get=1, create=0, update=0, delete=0, search=1, other=1
- **Action ids:** `filings.search`, `company.get`, `filings.recent`
- **Pack / seed:** demo_systems: executive-intelligence-pack; workflow/assignment refs: executive-intelligence-pack; templates: executive-intelligence-sources
- **Flags:** Note: catalog dept=finance but NOT Finance F3 (gravitree regulatory)

---

## 6. Out-of-catalog sources (detail)

### `crunchbase`

- **Status:** NOT in vendor_definitions.py. AuthMode GRAVITREE_MANAGED + ActivationGate GOVERNANCE_STOP_LINE (auth_mode.py). Config has crunchbase_api_key; docs mention CRUNCHBASE_BASE_URL but no connector module and no hardcoded api.crunchbase.com URL. v3->v4 migration NOT confirmed in this repo -- candidate Batch 1 only if product confirms API version + lifts governance stop-line. Contact-PII / Memory-KG STA-312.
- **API:** Unknown in code (no module). Industry default would be Crunchbase API v4 (api.crunchbase.com/v4) if/when implemented.
- **Packs:** Referenced as stop-line in sales/prospecting/CS installs; NOT in demo_systems or templates
- **Flag:** CONTACT_PII + GOVERNANCE_STOP_LINE

### `world_bank`

- **Status:** NOT in vendor_definitions.py. Gravitree-managed executive source.
- **API:** https://api.worldbank.org/v2 (WORLDBANK_BASE_URL / config)
- **Packs:** executive-intelligence-sources template; assignment in executive-intelligence-pack; NOT in demo_systems (demo is fred+sec_edgar only)
- **Flag:** LOW_GOVERNANCE public aggregate -- expansion candidate

### `oecd`

- **Status:** NOT in vendor_definitions.py. Gravitree-managed executive source.
- **API:** https://sdmx.oecd.org/public/rest/data (OECD_BASE_URL / config)
- **Packs:** executive-intelligence-sources template; assignment in executive-intelligence-pack; NOT in demo_systems
- **Flag:** LOW_GOVERNANCE public aggregate -- expansion candidate

### `opencorporates`

- **Status:** NOT in vendor_definitions.py. ActivationGate COMMERCIAL_LICENSE_PENDING.
- **API:** OPENCORPORATES_BASE_URL + token (config/env)
- **Packs:** executive-intelligence-sources template only
- **Flag:** LICENSE_BLOCKED

---

## 7. Phase 1 ranked expansion order

### Ranking rules (from Phase 0 brief)

1. Low-governance proven live first: Apollo, HubSpot, Slack, GitHub, Salesforce, Asana, Pipedrive, EngageBay, NVD, CISA KEV, FRED, SEC EDGAR, World Bank, OECD, GSC
2. Crunchbase v3->v4 = **candidate Batch 1 if confirmed** (currently **not** confirmed in repo)
3. Finance F3 / HR H3 **EXCLUDED** until live-invoke DONE
4. Contact-PII (`crunchbase`, `pdl`): catalog-ok where present; Memory/KG still STA-312
5. **One connector per batch**

### Batch plan (1..N)

| Batch | Vendor | Rationale |
|------:|--------|-----------|
| 1 | `crunchbase` *(CONDITIONAL)* | Candidate #1 **only if** API v4 confirmed + GOVERNANCE_STOP_LINE lifted + first `build_vendor` added. **Today: NOT confirmed** -- skip until product sign-off. |
| 2 | `apollo` | Proven live prospecting path; packs + seed; expand beyond search/list (enrichment, sequences) on stable api/v1. |
| 3 | `hubspot` | Highest pack fan-out (marketing/revops/sales/prospecting/CS); CRM v3 already live; expand tickets/lists/companies coverage carefully (writes need approval gates). |
| 4 | `slack` | Low-governance ops notify path; seed workflows already use `slack.post_message`. |
| 5 | `github` | Shipped ops connector; api.github.com REST; expand issues/PRs/actions reads first. |
| 6 | `salesforce` | Shipped CRM; pin-aware (v59.0); RevOps template optional; expand SOQL/search coverage. |
| 7 | `asana` | Shipped project tool; api/1.0 profile; expand tasks/projects after CRM/chat/dev. |
| 8 | `pipedrive` | Shipped CRM alternate; api/v1 aligned with docs; smaller action set -> clear expansion surface. |
| 9 | `engagebay` | Shipped lighter CRM; small action surface (6); good quick win after Pipedrive. |
| 10 | `nvd` | Gravitree-managed MSP; only 3 catalog actions -- expand search/recent with live evidence. |
| 11 | `cisa_kev` | Paired MSP feed; expand lookup/diff after NVD pattern proven. |
| 12 | `fred` | Executive macro; gravitree-managed (not F3); expand search/observations. |
| 13 | `sec_edgar` | Executive regulatory; requires SEC_USER_AGENT; expand company index / recent. |
| 14 | `world_bank` | Out-of-catalog today -- add `build_vendor` + actions on api.worldbank.org/v2 (already in executive template). |
| 15 | `oecd` | Out-of-catalog today -- add catalog + SDMX actions after World Bank pattern. |
| 16 | `google_search_console` | Marketing pack demo; note docs v1 vs runtime webmasters/v3; expand sitemaps/analytics dims. |
| 17 | `zendesk` | CS pack demo; support reads live path -- expand after core CRM/ops/MSP/exec. |
| 18 | `google_analytics` | Marketing pack demo; GA4 Data API -- expand after GSC. |
| 19 | `notion` / `jira` / `confluence` | Shipped knowledge/work trackers -- batch as separate one-connector runs in this order if capacity remains. |
| 20 | `ahrefs` / `semrush` / `finseo` / `pdl` | BYO premium -- expand only after tenant BYO paths evidenced; PDL Memory/KG remains STA-312. |
| G+ | Finance F3 + HR H3 | **GOVERNANCE_LAST** -- unlock only after F3/H3 live-invoke DONE with audit evidence. Then one connector per batch: QB -> Xero -> NetSuite -> Plaid; Greenhouse -> BambooHR -> Workday -> Gusto. |
| X | Unshipped catalog vendors | mailchimp, mixpanel, teams, outlook, twilio, sendgrid, airtable, zapier, n8n, motion, freshdesk, gorgias, adp, aws_s3, mongodb, snowflake, absorb_lms, stackadapt, hootsuite -- ship+smoke before action expansion. |

### Top 10 executable batches (assuming Crunchbase still blocked)

If Batch 1 Crunchbase remains blocked (current state), execute:

1. **Apollo**
2. **HubSpot**
3. **Slack**
4. **GitHub**
5. **Salesforce**
6. **Asana**
7. **Pipedrive**
8. **EngageBay**
9. **NVD**
10. **CISA KEV**

(Next: FRED -> SEC EDGAR -> World Bank -> OECD -> GSC.)

---

## 8. Unshipped vendors (shipped=False)

| Vendor | Department | Actions |
|--------|------------|--------:|
| `mailchimp` | marketing | 9 |
| `mixpanel` | marketing | 8 |
| `hootsuite` | marketing | 8 |
| `stackadapt` | marketing | 8 |
| `microsoft_teams` | operations | 8 |
| `outlook` | operations | 8 |
| `twilio` | operations | 8 |
| `sendgrid` | operations | 8 |
| `airtable` | operations | 8 |
| `zapier` | operations | 8 |
| `n8n` | operations | 8 |
| `motion` | operations | 8 |
| `freshdesk` | support | 9 |
| `gorgias` | support | 9 |
| `adp` | operations | 8 |
| `aws_s3` | operations | 8 |
| `mongodb` | operations | 8 |
| `snowflake` | operations | 8 |
| `absorb_lms` | operations | 8 |

---

## 9. Phase 0 exit criteria

- [x] All `build_vendor` entries enumerated with shipped/dept/docs/actions
- [x] Pack `demo_systems` + templates + seed references mapped
- [x] Finance/HR flagged GOVERNANCE_LAST
- [x] Contact-PII / STA-312 called out for PDL + Crunchbase
- [x] Crunchbase v3->v4 status documented (**not confirmed in repo**)
- [x] One-connector-per-batch Phase 1 order produced
- [ ] Phase 1 implementation starts only after human picks Batch N


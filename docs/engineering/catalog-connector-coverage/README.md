# Catalog connector coverage

Engineering implementation, pending live activation. Requested by the owner to
fill connector gaps across agents, workflows, plays and packages. No live account
grants, agent permissions or workflow definitions were changed by this patch.

`coverage.json` maps 763 source entries to 114 declared connector dependencies:
150 marketplace seed entries, 106 outcome-manifest entries, nine static plays,
348 connector workflow examples and a read-only live snapshot of 73 published
assets, 28 saved agents and 49 saved workflows. These sources overlap; 763 is
not a unique product count. There were no saved capability packages or play
installations in the inspected owner workspaces. Private names, identifiers,
prompts and credentials are omitted from the report.

The extractor follows structured connector requirements and registered action
prefixes, including serialized nested configs. It does not invent dependencies
from prose or authorize actions. Required connector groups retain their source
paths, so alternatives must not be interpreted as mandatory simultaneous grants.

## Added or upgraded OAuth paths

| Vendor | Target Nango integration | Provider template |
| --- | --- | --- |
| Freshservice | gravitre-freshservice-oauth | freshservice-oauth |
| Gong | gravitre-gong-oauth | gong-oauth |
| HiBob | gravitre-hibob-oauth | hibob-oauth |
| Cal.com | gravitre-cal-com-oauth | cal-com-oauth |
| BambooHR | gravitre-bamboohr | bamboohr |
| Greenhouse | gravitre-greenhouse-harvest | greenhouse-harvest-partner |
| Ahrefs | gravitre-ahrefs | ahrefs |
| Linear | gravitre-linear | linear |
| GitLab | gravitre-gitlab | gitlab |
| Shopify | gravitre-shopify | shopify |
| PayPal | gravitre-paypal | paypal |
| Meta Marketing | gravitre-meta-marketing | facebook |

`provider-templates.json` records the reviewed upstream templates and source hash.
App credentials, provider review and account consent remain separate requirements.
Greenhouse partner OAuth specifically requires a provider partnership. Ahrefs
subscription entitlements remain enforced; OAuth does not create an API entitlement.
GitLab's new template targets GitLab.com. Greenhouse managed reads use Harvest v3;
native API-key reads retain v1 and v3 records are not synthesized into v1 shapes.

Existing Freshservice/Gong/HiBob/Cal.com connection identities remain allowlisted
for execution, health checks and deletion. New consent starts against the OAuth
integration and only a matching signed webhook activates it. A cancelled attempt
does not replace a working connection. Old remote connections are not deleted
automatically. Native BambooHR/Greenhouse/Ahrefs and other native grants remain
usable until that account explicitly completes managed consent.

Slack, Google Ads and Google Analytics stay native. Clio's existing native OAuth
entry was restored to the picker after its live configuration check succeeded.
Aircall retains its existing managed route; it was not verified as native.

## Remaining dependencies requiring a different decision

| Dependency | Finding |
| --- | --- |
| Brevo | Existing backend uses an API key; reviewed Nango template is API-key-only. |
| ConnectWise | Existing backend; reviewed Nango template is Basic auth. |
| EngageBay | Existing backend; no reviewed Nango OAuth template found. |
| FHIR, real_estate | Generic adapters need a specific provider and authorization contract. |
| platform, webhook, vapi | Internal execution or voice infrastructure, not missing customer OAuth cards. |

Other existing specialized or noninteractive connectors remain identified in the
report. A template or catalog card is not proof of working account authorization
or of every advertised action being implemented.

## Activation

Live provisioning was blocked on 2026-11-05: Nango API authentication returned
401 and the dashboard presented sign-in. No live integration creation is claimed.
Restore secure Nango access, select the intended environment, then run this
read-only inventory using an environment-supplied `NANGO_SECRET_KEY`:

```sh
python scripts/nango-connector-setup.py --oauth-only \
  --vendor freshservice --vendor gong --vendor hibob --vendor cal_com \
  --vendor bamboohr --vendor greenhouse --vendor ahrefs --vendor linear \
  --vendor gitlab --vendor shopify --vendor paypal --vendor meta_marketing \
  --output /tmp/catalog-nango-inventory.json
```

Repeat with `--apply` to create only missing exact integration configurations.
The script never overwrites existing app credentials. Complete each provider app
configuration and any required review, then authorize each account through
Gravitre's headless connection UI. Verify a signed webhook and a scoped read
action before marking that account live. New agent/workflow authority is not
automatically granted by adding a connector.

Regenerate repository coverage without private data:

```sh
python scripts/audit-catalog-connector-dependencies.py \
  --output /tmp/catalog-coverage.json
```

The optional `--live-inventory` adds a locally supplied snapshot; raw snapshots
must not be committed. Production acceptance is NOT RUN: this branch is not
deployed and live Nango access is unavailable. Full CI must pass before merge.

## Local verification

- Connector/router/service regression: 602 passed, one skipped (603 collected).
- Web unit suite: 2,016 passed across 320 files.
- Web lint, typecheck and production build: passed.
- Generated 91-entry managed catalog, whitespace, status-leak and brand guards: passed.
- The full backend, PostgreSQL/Redis acceptance and integration smoke remain CI gates.

Existing assertions were updated deliberately: Freshservice now has interactive
OAuth (the noninteractive control uses Ashby instead); Linear now has an opt-in
managed path, asserted as OAuth with native fallback; the picker count increased
from 83 to 91. The assertions were not relaxed to mask missing implementations.

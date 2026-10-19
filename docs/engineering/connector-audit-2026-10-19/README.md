# Connector and OAuth audit — 2026-10-19

This audit covers 167 vendor identities across the frontend picker (153 options), backend action catalog (117 vendors), native OAuth registry, managed registry and current account inventory. Configuration readiness, recorded account health, registered code and live account acceptance are separate evidence. No customer accounts were authorized, migrated or deleted during this audit.

## Live findings

- Native OAuth readiness: 44 status endpoints responded HTTP 200; 34 report configured and all report encryption configured. Missing app configuration: GitLab, Hootsuite, Linear, Marketo, Meta Marketing, NetSuite, PayPal, Shopify, Workday and Zapier. These are configuration checks, not completed OAuth grants.
- Account health: 41 undeleted accounts; 14 connected, 3 auth_expired (one each Slack, Google Ads and Google Analytics), 9 pending_auth, 1 pending_property, 14 without recorded health evidence. Connected Google accounts also exist; the expired grants do not establish a provider-wide outage.
- Nango initially had only github-getting-started. Provisioning created 78 exact provider configurations without overwriting existing apps or credentials. The original demo remains. Readback confirms 36 ready for account authorization/credential collection, 42 requiring OAuth app credentials, and 2 unsupported providers (Syncro, Recurly). Readiness is not a live customer connection.
- Existing ClickHouse hostname mtnotvcshp.us-west-2.aws.clickhouse.cloud still fails DNS in current Railway startup logs; Postgres fallback is active. This is an infrastructure issue, separate from OAuth. No replacement hostname was available.

## Changes

- Added 30 business connector picker entries, official provider logo assets and one bounded GET executor per connector. Managed picker options total 77. Actions use canonical permissions, organization/environment scoping, rate limits and audit through invoke_tool. No generic caller-selected proxy URLs or methods are exposed.
- Added provider-specific setup checks: a platform Nango key alone no longer enables every provider. Missing integration, wrong template, absent app credentials and inventory failure block connection creation before tenant mutation. Corrected mismatched template names for HiBob, SAP, Help Scout, HaloPSA, Duo, 1Password Events and Jamf. Syncro/Recurly fail closed.
- Added explicit Nango reauthorization fallback for Slack, Google Ads and Google Analytics. Healthy native grants keep their auth path. Signed activation switches the account only after the current attempt succeeds; cancellation preserves native authorization/configuration. Managed tokens are passed in memory to existing executors; refresh tokens are never copied back to native secret storage.
- Managed health now validates remotely in the scheduled monitor, detects refresh errors and can recover previously erroneous accounts.
- New vendors use the existing custom storage type plus explicit vendor identity; no production schema migration is required.

## Added business connectors

| Department | Connector | Implemented read |
| --- | --- | --- |
| support | Aircall | `users.list` — `GET /v1/users` |
| engineering | Bitbucket | `profile.get` — `GET /2.0/user` |
| operations | Cal.com | `profile.get` — `GET /v2/me` |
| engineering | DigitalOcean | `account.get` — `GET /v2/account` |
| support | Discourse | `categories.list` — `GET /categories.json` |
| security | Drata | `personnel.list` — `GET /public/personnel` |
| hr | Factorial | `employees.list` — `GET /api/2026-10-01/resources/employees/employees` |
| finance | Harvest | `profile.get` — `GET /v2/users/me` |
| hr | Humaans | `people.list` — `GET /api/people` |
| legal | Ironclad | `workflows.list` — `GET /public/api/v1/workflows` |
| marketing | Klaviyo | `lists.list` — `GET /api/lists/` |
| sales | Lemlist | `campaigns.list` — `GET /api/campaigns` |
| analytics | Metabase | `profile.get` — `GET /api/user/current` |
| it | NinjaOne | `devices.list` — `GET /v2/devices` |
| legal | PandaDoc | `documents.list` — `GET /public/v1/documents` |
| operations | Productboard | `features.list` — `GET /v2/entities` |
| finance | Recharge | `customers.list` — `GET /customers` |
| operations | Smartsheet | `profile.get` — `GET /2.0/users/me` |
| operations | Teamwork | `projects.list` — `GET /projects.json` |
| marketing | Typeform | `forms.list` — `GET /forms` |
| marketing | Webflow | `sites.list` — `GET /v2/sites` |
| operations | Wrike | `contacts.list` — `GET /api/v4/contacts` |
| operations | Toggl Track | `profile.get` — `GET /api/v9/me` |
| operations | Todoist | `projects.list` — `GET /api/v1/projects` |
| engineering | Sentry | `organizations.list` — `GET /api/0/organizations/` |
| sales | Freshsales | `contacts.get` — `GET /api/contacts/{contact_id}` |
| design | Miro | `boards.list` — `GET /v2/boards` |
| finance | Pennylane | `customers.list` — `GET /api/external/v2/customers` |
| hr | TalentLMS | `users.list` — `GET /api/v2/users` |
| marketing | Contentful | `spaces.list` — `GET /spaces` |

Harvest requires a Harvest account ID. Freshsales requires a contact ID. Pennylane uses company-scoped credentials; firm-level tokens requiring extra company routing are not supported by this slice. Multi-account/domain/region constraints and sufficient scopes must be checked during account-owner acceptance. Each definition links its official API reference in managed_business_connectors.json. These adapters implement initial reads; they do not imply complete write/sync coverage.

## Remaining external setup and acceptance

1. Supply provider OAuth client ID/secret and required scopes for each of the 42 integrations listed as provider_credentials_required in nango-readback.json. Register the Nango Cloud callback https://api.nango.dev/oauth/callback with those provider apps. App verification/partner approvals remain provider-dependent. Native app credentials cannot simply be assumed valid for the Nango callback.
2. Account owners must connect or reauthorize through Gravitre. Slack, Google Ads and Google Analytics expired accounts remain expired until consent succeeds. Selecting Nango does not repair a revoked grant without consent.
3. Run owner acceptance for each enabled account: connect, signed webhook activation, real read, refresh, reconnect, cancellation and removal. **NOT_RUN — no owner account authorization/session available; OAuth app credentials missing for 42 integrations.** No live action tests were claimed.
4. Resolve the existing ClickHouse DNS endpoint and the 14 accounts with no health evidence. Do not mark them healthy based on active/syncing labels.
5. The older 45 managed options outside Freshservice/Okta still provide authorization paths only, subject to setup; actions remain pending. The CSV exposes inferred routes elsewhere in the older backend catalog. Registered executors and inferred routes are not vendor/live validation.

## Evidence and verification

- [All connector audit rows](all-connectors.csv): frontend option flag, catalog/registered action counts, inferred route counts, prior vendor-validation markers, OAuth configuration, Nango setup and account health. Owner tests are NOT_RUN, independent of historical source-map markers.
- [Native OAuth status responses](native-oauth-readiness.json), [account health aggregates](account-health.json), [Nango readback](nango-readback.json), [summary](summary.json), [official logo provenance](provider-logo-sources.json). Reports contain no account identifiers or credentials.
- Local frontend: 1,868 tests pass; TypeScript and optimized Next.js build pass. Changed-file ESLint has 0 errors (10 existing warnings).
- Local backend connector and related contracts: 570 passed, 1 skipped; includes tenant/environment isolation, credential boundaries, provider-specific setup, cancellation/activation and all 30 fixed read adapters.
- Full CI and exact production deployment alignment must be verified on the published commit; local checks do not establish live account acceptance.

## Reproduce provider configuration audit

Run scripts/nango-connector-setup.py with NANGO_SECRET_KEY in the environment and --output PATH. Default is read-only. --apply creates missing exact integration configurations only, never updates existing app credentials. Generated managed frontend metadata comes from scripts/generate-managed-connector-catalog.py; logo registry comes from apps/web/scripts/build-provider-registry.mjs.

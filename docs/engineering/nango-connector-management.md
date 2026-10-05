# Nango connector management implementation and activation

Status on 2026-10-05: implementation verified locally; production activation NOT RUN.

Gravitre owns permissions, approvals, audit and workflow execution. Nango handles authorization, credential storage/refresh and authenticated proxy requests. Existing native OAuth providers keep their current auth paths.

## Implemented flow

- All 47 registered managed providers are included in the connector picker. Account authorization is distinguished from executable workflow action support.
- Add/reconnect launches the Nango frontend SDK with a server-issued session token. The UI waits for the signed webhook to confirm that exact authorization attempt before reporting success.
- Reconnect keeps the previous connection ID and provider configuration; cancellation does not deactivate an already active account. It uses Nango's reconnect session endpoint.
- Session/status queries are tenant/environment scoped. The webhook verifies the raw-body HMAC, provider mapping, managed routing and current attempt; activation updates are conditional on the current attempt. Deleted rows cannot be reactivated.
- Canonical health recognizes managed connections. Live tests use Nango's current /connections/{id} endpoint and validate returned connection/integration IDs and auth errors.
- Confirmed removal deletes the Nango connection before soft deletion. If remote removal fails, the row is retained for retry. A missing Nango connection is idempotent.
- Freshservice has three reads and one governed status write; Okta has five read actions. Both use the canonical Gravitre tool registry. No generic arbitrary-URL proxy action is exposed.

## Production activation required

Read-only Railway configuration inspection found NANGO_API_BASE_URL present, but neither NANGO_SECRET_KEY (or NANGO_API_KEY alias) nor NANGO_WEBHOOK_SIGNING_KEY present on the production gravitre-saas-backend service. No credentials were read or changed.

1. Set NANGO_SECRET_KEY and NANGO_WEBHOOK_SIGNING_KEY on that Railway service using the values from the correct Nango environment. Keep them backend-only. Nango API scopes must allow connect-session writes, connection reads/deletes and proxy requests.
2. Configure actual integrations in that Nango environment. Integration unique keys must match the provider mapping below; verify the Nango provider/auth method and configure required OAuth app credentials/scopes for each integration. Registry entries alone do not configure Nango or guarantee every API action.
3. Set Nango's outgoing webhook URL to https://gravitre-saas-backend-production.up.railway.app/api/connectors/managed-auth/webhook/nango and enable auth connection creation/reconnect notifications. Use the environment's webhook signing key, not the API secret key.
4. Apply/check supabase/migrations/20261001233000_add_nango_long_tail_connector_types.sql. This task verified registry coverage in the migration file; live database migration state was not verified.
5. Configure Connect UI branding for Gravitre in Nango, including the customer-facing logo/name, help links and removal of Nango attribution where available. Provider OAuth consent uses the configured OAuth application's identity. No OAuth app verification is implied by this implementation.
6. Deploy this PR's frontend and backend, then verify an owner-tenant connection, signed activation, read action, reconnect, cancellation and removal against real accounts. Verify the Freshservice write with explicit approval and follow-up source-of-record status read.

Do not classify this release as production verified until those live runs have evidence. The other 45 providers support the managed authorization path only; they need reviewed action contracts/executors before workflow execution can be claimed.

## Nango dashboard URLs

| Setting | Value |
| --- | --- |
| Auth Callback URL (Nango Cloud) | `https://api.nango.dev/oauth/callback` |
| Primary Webhook URL | `https://gravitre-saas-backend-production.up.railway.app/api/connectors/managed-auth/webhook/nango` |
| Secondary Webhook URL | Leave blank; no separate receiver is configured |

The callback is registered with each provider OAuth application. The primary webhook receives Nango auth events in Gravitre. A custom Gravitre callback would need a deployed redirect preserving query parameters; it is not configured here.

## Local validation

- Frontend: 1,366 tests passed; TypeScript passed; optimized Next.js production build passed (local deployment environment values were absent, so build success is not live acceptance).
- Backend: 113 relevant tests passed; one existing test skipped. Covers auth sessions, signed activation, reconnect/cancellation semantics, stale attempts, scope checks, deletion retries, live health response handling, action readiness, runtime execution and catalog/schema/enrichment gates.
- Live Nango/owner acceptance: NOT RUN, blocked by missing backend credentials.

## Provider support matrix

“Authorization path” means implementation wired, subject to actual Nango integration configuration and live verification. “Action support” means registered local executors, not production acceptance.

| Provider | Gravitre vendor | Nango integration key | Action support |
| --- | --- | --- | --- |
| ServiceNow | `servicenow` | `servicenow` | Authorization path only; actions pending |
| ConnectSecure | `connectsecure` | `connectsecure` | Authorization path only; actions pending |
| Sage Intacct | `sage_intacct` | `sage-intacct` | Authorization path only; actions pending |
| Front | `front` | `front` | Authorization path only; actions pending |
| Gong | `gong` | `gong` | Authorization path only; actions pending |
| HighLevel | `highlevel` | `highlevel` | Authorization path only; actions pending |
| Instantly | `instantly` | `instantly` | Authorization path only; actions pending |
| Attio | `attio` | `attio` | Authorization path only; actions pending |
| Close | `close` | `close` | Authorization path only; actions pending |
| Ashby | `ashby` | `ashby` | Authorization path only; actions pending |
| HiBob | `hibob` | `hibob` | Authorization path only; actions pending |
| UKG Pro | `ukg_pro` | `ukg-pro` | Authorization path only; actions pending |
| Box | `box` | `box` | Authorization path only; actions pending |
| Dropbox | `dropbox` | `dropbox` | Authorization path only; actions pending |
| Zoom | `zoom` | `zoom` | Authorization path only; actions pending |
| Discord | `discord` | `discord` | Authorization path only; actions pending |
| SAP S/4HANA Cloud | `sap_s4hana_cloud` | `sap-s4hana-cloud` | Authorization path only; actions pending |
| SharePoint Online | `sharepoint_online` | `sharepoint-online` | Authorization path only; actions pending |
| Freshservice | `freshservice` | `freshservice` | 4 ticket actions (status write requires approval) |
| Kustomer | `kustomer` | `kustomer` | Authorization path only; actions pending |
| Help Scout | `helpscout` | `help-scout` | Authorization path only; actions pending |
| Copper | `copper` | `copper` | Authorization path only; actions pending |
| Zoho CRM | `zoho_crm` | `zoho-crm` | Authorization path only; actions pending |
| Lever | `lever` | `lever` | Authorization path only; actions pending |
| Deel | `deel` | `deel` | Authorization path only; actions pending |
| Rippling | `rippling` | `rippling` | Authorization path only; actions pending |
| Personio | `personio` | `personio` | Authorization path only; actions pending |
| Ramp | `ramp` | `ramp` | Authorization path only; actions pending |
| Brex | `brex` | `brex` | Authorization path only; actions pending |
| Chargebee | `chargebee` | `chargebee` | Authorization path only; actions pending |
| DocuSign | `docusign` | `docusign` | Authorization path only; actions pending |
| Dropbox Sign | `dropbox_sign` | `dropbox-sign` | Authorization path only; actions pending |
| Pax8 | `pax8` | `pax8` | Authorization path only; actions pending |
| Autotask PSA | `autotask` | `autotask` | Authorization path only; actions pending |
| HaloPSA | `halo_psa` | `halopsa` | Authorization path only; actions pending |
| Syncro | `syncro` | `syncro` | Authorization path only; actions pending |
| Huntress | `huntress` | `huntress` | Authorization path only; actions pending |
| SentinelOne | `sentinelone` | `sentinelone` | Authorization path only; actions pending |
| CrowdStrike | `crowdstrike` | `crowdstrike` | Authorization path only; actions pending |
| Okta | `okta` | `okta` | 5 identity read actions |
| JumpCloud | `jumpcloud` | `jumpcloud` | Authorization path only; actions pending |
| Duo | `duo` | `duo` | Authorization path only; actions pending |
| 1Password | `onepassword` | `1password` | Authorization path only; actions pending |
| Microsoft Intune | `microsoft_intune` | `microsoft-intune` | Authorization path only; actions pending |
| Jamf Pro | `jamf_pro` | `jamf-pro` | Authorization path only; actions pending |
| Braintree | `braintree` | `braintree` | Authorization path only; actions pending |
| Recurly | `recurly` | `recurly` | Authorization path only; actions pending |

## References and maintenance

Nango documentation: [connect sessions](https://nango.dev/docs/reference/backend/http-api/connect/sessions/create), [reconnect sessions](https://nango.dev/docs/reference/backend/http-api/connect/sessions/reconnect), [connection health](https://nango.dev/docs/reference/backend/http-api/connections/get), [connection deletion](https://nango.dev/docs/reference/backend/http-api/connections/delete).

Regenerate the frontend catalog with `python scripts/generate-managed-connector-catalog.py` after updating the canonical backend registry. Tests verify catalog/migration parity.

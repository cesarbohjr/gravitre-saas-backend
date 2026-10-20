# Gravitre-owned OAuth activation — 2026-10-20

## Implemented

Gravitre renders the account configuration and sign-in confirmation screens. Nango's headless frontend SDK opens the provider login directly; the hosted Connect UI is no longer used. The SDK is loaded only on demand. A direct user click starts the popup after session preparation, avoiding async popup blocking. Closing provider sign-in cancels; errors use Gravitre copy. Reconnect uses a scoped reconnect token and preserves account identity. Only the matching signed webhook activates the account.

New managed sessions allow interactive OAUTH1/OAUTH2 only. API_KEY, BASIC, OAUTH2_CC and TWO_STEP configurations are unavailable for new connection/reconnection through this flow. Existing accounts and execution are not deleted or migrated. This does not convert non-OAuth providers or change native connectors' existing authentication paths.

Provider domain, account and region inputs are allowlisted and validated before creating any connector row. Automated and secret provider fields are excluded. The schema is reviewed from NangoHQ/nango `packages/providers/providers.yaml` on 2026-10-20. New provider schemas require review before exposure.

## Callback

Production callback to register: **https://gravitre.app/api/connectors/oauth/callback**

This public GET endpoint issues a fixed-destination 308 redirect to Nango Cloud, preserving the query string, with no-store and no-referrer headers. It accepts no configurable redirect target. Nango validates OAuth state. Provider grants and the environment callback are not modified merely by deploying this route.

## Activation still required

1. Register or verify a **Gravitre-owned OAuth app** with each provider. Use Gravitre's name, logo, support/privacy URLs, authorized scopes and the callback above. Complete any provider verification before public release. Do not use shared/demo developer apps for branded production consent.
2. Store each app's client ID and secret in the matching Nango integration, not customer input forms or source control.
3. After the callback endpoint is live and provider registrations accept it, change the existing Nango environment's callback in **Environment Settings > Backend**. This is dashboard-only for existing environments. Audit all other integrations in that environment before switching the global callback; retain old allowed callbacks during transition where the provider permits them.
4. Run owner-account authorization, signed webhook delivery, read, refresh, reconnect and removal acceptance for each provider. Do not count configured templates as working accounts.

**Blocked:** the Nango dashboard in this session redirects to sign-in. Provider developer-account sessions/app credentials are not available for the 42 interactive OAuth configurations. No provider app was created or claimed verified, and the environment callback was not switched. Live owner-grant acceptance remains NOT RUN.

The Oct19 readback had 42 interactive OAuth configurations missing app credentials, 36 configurations using other credential methods, and 2 unsupported templates. Under OAuth-only readiness, none of those 36 counts as ready for user sign-in. Existing native OAuth grants are separate and unchanged.

## Provider registration checklist

All rows below need Gravitre app credentials/identity verification and live owner-account acceptance. Integration keys remain stable; no existing accounts were automatically migrated.

| Provider | Nango integration key | Status |
| --- | --- | --- |
| servicenow | `servicenow` | App setup and live acceptance pending |
| front | `front` | App setup and live acceptance pending |
| highlevel | `highlevel` | App setup and live acceptance pending |
| attio | `attio` | App setup and live acceptance pending |
| close | `close` | App setup and live acceptance pending |
| box | `box` | App setup and live acceptance pending |
| dropbox | `dropbox` | App setup and live acceptance pending |
| zoom | `zoom` | App setup and live acceptance pending |
| discord | `discord` | App setup and live acceptance pending |
| sharepoint_online | `sharepoint-online` | App setup and live acceptance pending |
| helpscout | `help-scout` | App setup and live acceptance pending |
| copper | `copper` | App setup and live acceptance pending |
| zoho_crm | `zoho-crm` | App setup and live acceptance pending |
| lever | `lever` | App setup and live acceptance pending |
| deel | `deel` | App setup and live acceptance pending |
| ramp | `ramp` | App setup and live acceptance pending |
| brex | `brex` | App setup and live acceptance pending |
| docusign | `docusign` | App setup and live acceptance pending |
| dropbox_sign | `dropbox-sign` | App setup and live acceptance pending |
| okta | `okta` | App setup and live acceptance pending |
| braintree | `braintree` | App setup and live acceptance pending |
| aircall | `aircall` | App setup and live acceptance pending |
| bitbucket | `bitbucket` | App setup and live acceptance pending |
| digitalocean | `digitalocean` | App setup and live acceptance pending |
| factorial | `factorial` | App setup and live acceptance pending |
| harvest | `harvest` | App setup and live acceptance pending |
| ironclad | `ironclad` | App setup and live acceptance pending |
| ninjaone | `ninjaone` | App setup and live acceptance pending |
| pandadoc | `pandadoc` | App setup and live acceptance pending |
| productboard | `productboard` | App setup and live acceptance pending |
| smartsheet | `smartsheet` | App setup and live acceptance pending |
| teamwork | `teamwork` | App setup and live acceptance pending |
| typeform | `typeform` | App setup and live acceptance pending |
| webflow | `webflow` | App setup and live acceptance pending |
| wrike | `wrike` | App setup and live acceptance pending |
| todoist | `todoist` | App setup and live acceptance pending |
| miro | `miro` | App setup and live acceptance pending |
| pennylane | `pennylane` | App setup and live acceptance pending |
| contentful | `contentful` | App setup and live acceptance pending |
| slack | `gravitre-slack` | App setup and live acceptance pending |
| google_ads | `gravitre-google-ads` | App setup and live acceptance pending |
| google_analytics | `gravitre-google-analytics` | App setup and live acceptance pending |

## Branding boundary

Normal customer UI uses Gravitre and provider names. Nango infrastructure remains discoverable through network inspection and the callback redirect. Do not describe it as technically undetectable. Provider consent identity and custom callback activation remain external prerequisites.

Official references: [headless auth](https://nango.dev/docs/guides/auth/customize-connect-ui), [frontend SDK](https://nango.dev/docs/reference/frontend/frontend-sdk), [callback and owned OAuth apps](https://nango.dev/docs/guides/auth/auth-guide).

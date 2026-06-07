# Connector Auth Production Readiness

Last updated: production-readiness pass for Gravitre connector/OAuth architecture.

## Auth matrix

| Class | Examples | Platform env | Per-connector |
|-------|----------|--------------|---------------|
| Standard OAuth2 | Mailchimp, Asana, Intercom, Monday | `{VENDOR}_CLIENT_ID/SECRET` | OAuth tokens (encrypted) |
| OAuth2 + PKCE | Airtable, Canva, Xero | `{VENDOR}_CLIENT_ID/SECRET` | OAuth tokens |
| OAuth2 custom | Workday, NetSuite, Marketo, Microsoft 365, Odoo | Dedicated or `{VENDOR}_*` | Tenant/subdomain/instance fields |
| Dual OAuth + API key | GitHub, Zendesk | Optional `GITHUB_*`, `ZENDESK_*` | PAT/API token **or** OAuth tokens |
| API key / token | SendGrid, Twilio, Mixpanel, Apollo, Segment | None | Encrypted secrets |
| Connection string | PostgreSQL, MongoDB | None | Connection string |
| IAM | AWS S3 | None | Access key + secret + region |
| Plaid Link | Plaid | `PLAID_CLIENT_ID`, `PLAID_SECRET` | `public_token` exchange |
| Platform AI | Claude/Anthropic | `ANTHROPIC_API_KEY` | N/A (not a connector) |
| Partner-gated | ADP, Gusto, Hootsuite, Zapier, Canva | After partner approval | Partner credentials |

## OAuth providers (generic registry)

`zapier`, `mailchimp`, `constant_contact`, `hootsuite`, `xero`, `airtable`, `asana`, `clickup`, `freshdesk`, `intercom`, `github`, `monday`, `gusto`, `odoo`, `canva`, `microsoft365`, `zendesk`

Tier 1–3 dedicated modules: HubSpot, Salesforce, QuickBooks, NetSuite, Jira, Confluence, PagerDuty, Notion, Workday, Marketo, Google vendors.

## PKCE providers

**Required:** `airtable`, `canva`, `xero`

Implementation: RFC 7636 S256 in `oauth_pkce.py`; verifier stored in signed OAuth state; `code_verifier` sent on token exchange.

## API-key providers

`segment`, `stripe`, `linkedin`, `mixpanel`, `semrush`, `stackadapt`, `apollo`, `sendgrid`, `twilio`, `n8n`, `motion`, `bamboohr`, `absorb_lms`, `gorgias`, `snowflake` (password/key-pair), `adp`

## Database connectors

`postgresql`, `mongodb` — connection string per connector.

## IAM connectors

`aws_s3` — access key id, secret access key, region, bucket per connector.

## Partner-gated connectors

`adp`, `gusto`, `hootsuite`, `zapier`, `canva` — catalog `requiresPartnerApproval: true`; not self-serve instant connect.

## Required platform environment variables

### Always (connectors enabled)

- `CONNECTOR_SECRETS_ENCRYPTION_KEY`
- `API_PUBLIC_URL` (OAuth callbacks)

### Platform AI (not connector OAuth)

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`

### Verified generic OAuth apps

`ZAPIER_*`, `MAILCHIMP_*`, `CONSTANT_CONTACT_*`, `HOOTSUITE_*`, `XERO_*`, `AIRTABLE_*`, `ASANA_*`, `CLICKUP_*`, `FRESHDESK_*`, `INTERCOM_*`, `GITHUB_*`, `MONDAY_*`, `GUSTO_*`, `ODOO_*`, `CANVA_*`, `MICROSOFT365_*`, `ZENDESK_*`

### Tier 1–3 (see `backend/.env.example`)

HubSpot, Salesforce, QuickBooks, NetSuite, Jira, Confluence, PagerDuty, Notion, Workday, Marketo, Google OAuth.

### Plaid (Link, not OAuth callback)

- `PLAID_CLIENT_ID`
- `PLAID_SECRET`

## Per-connector setup fields

| Vendor | Fields |
|--------|--------|
| Zendesk | subdomain + (email + API token) **or** OAuth |
| GitHub | owner, repo + PAT **or** OAuth |
| Snowflake | account, warehouse, database, schema, role, auth_method (`password` / `key_pair`; OAuth gated) |
| Odoo | instanceUrl + OAuth or API key |
| PostgreSQL / MongoDB | connection string |
| AWS S3 | access key, secret, region, bucket |

## OAuth security

- Signed state with `jti`, `nonce`, org/user/vendor binding
- One-time `jti` consumption (replay protection)
- 10-minute expiry
- Tokens encrypted at rest via `CONNECTOR_SECRETS_ENCRYPTION_KEY`
- Tokens never logged (only error types in logs)

## Remaining risks

1. **Snowflake OAuth** — config schema exists; OAuth connect flow not production-ready
2. **Partner apps** — Hootsuite/Gusto/Zapier/Canva need partner approval before customer use
3. **Plaid Link** — frontend Link UI + public_token exchange endpoint not fully implemented
4. **Microsoft 365** — tenant admin consent may block multi-tenant apps
5. **Odoo** — self-hosted variance (OAuth vs API key)

## Related documentation (master audit suite)

- `docs/CONNECTOR_IMPLEMENTATION_MATRIX.md` — master matrix, redirect registry, scopes, executive dashboard
- `docs/CONNECTOR_CREDENTIAL_ACQUISITION_PLAYBOOK.md` — operator playbooks + `.env` template
- `docs/CONNECTOR_PRODUCTION_READINESS_REPORT.md` — audit findings, HubSpot gold standard, issue register
- `docs/CONNECTOR_ROADMAP.md` — phases, top-15 launch set, engineering milestones

## Launch readiness checklist

- [ ] `CONNECTOR_SECRETS_ENCRYPTION_KEY` set in production
- [ ] `API_PUBLIC_URL` matches OAuth redirect URIs registered at each vendor
- [ ] PKCE apps (Airtable, Canva, Xero) tested end-to-end
- [ ] GitHub/Zendesk tested with OAuth and API-key fallbacks
- [ ] No `CLAUDE_CLIENT_*` or fake OAuth env vars for API-key vendors
- [ ] Plaid uses Link flow only
- [ ] Snowflake connectors created with `auth_method: password` or `key_pair` only
- [ ] Partner-gated vendors documented for sales/onboarding

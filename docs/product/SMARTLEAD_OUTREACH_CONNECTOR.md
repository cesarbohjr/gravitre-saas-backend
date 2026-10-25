# Smartlead outbound connector (WIP, safe-by-default)

Smartlead was selected for dedicated cold-email sequences, scheduling,
mailbox rotation, replies, analytics, and unsubscribes. API access depends on
the connected account plan. See https://helpcenter.smartlead.ai/en/articles/125-full-api-documentation

## Supported now
- `smartlead.campaigns.list` (read-only)
- `smartlead.email_accounts.list` (read-only)
- `smartlead.analytics.overview` (read-only)
- `smartlead.leads.enroll`: registered but intentionally denies execution.

All reads use the existing Gravitre tenant-scoped connector vault key `api_key`,
an org-scoped active connector of type `smartlead`, explicit `outreach_enabled`,
and a fixed Smartlead API hostname. No keys appear in logs or returns.

## Blocking requirements before enrollment becomes executable
1. A registered and authorized sender mailbox with SPF, DKIM and DMARC;
   source/destination data region permitted by the customer.
2. Human-reviewed and still-valid consent evidence under CASL or the applicable
   law, including required identity, postal address and unsubscribe information.
3. Global and tenant suppression lookup, including previous unsubscribes,
   complaints and bounces; synchronizing Smartlead block lists.
4. Canonical PendingAction approval **for the exact campaign, contacts and
   content**. An active Smartlead campaign can send immediately upon enrollment.
5. Idempotent enrollment and rollback/reconciliation for ambiguous delivery.
6. Authenticated and verified webhooks for replies, bounces, unsubscribes,
   spam complaints and campaign status; immediately suppress all follow-ups.
7. Provider contract tests and live production E2E using only permissioned
   test recipients. No unsolicited production sends in acceptance tests.

This PR does **not** activate sending or authorize adding contacts to campaigns.

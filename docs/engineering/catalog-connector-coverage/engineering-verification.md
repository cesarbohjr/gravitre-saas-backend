# Engineering connector verification

Scope: the nine engineering connectors requested by the owner. Implementation
is on PR #604; this report does not claim a merge or production deployment.

| Connector | Implemented actions | Live finding |
| --- | --- | --- |
| Linear | Issue create/get/list/search/update | Nango dev OAuth configuration exists; zero connections; app credentials/scopes and consent pending. Native status reports unconfigured, as expected for the selected managed route. |
| GitLab | Projects list; issues list/create; merge requests list/create | Nango dev OAuth configuration exists; zero connections; app credentials/scopes and consent pending. Managed template targets GitLab.com. |
| GitHub | Repository read, issues, pull requests, releases, Actions | Production native OAuth status HTTP 200, configured=true; no saved account in the inspected workspaces. |
| Jira | Projects/users, issue reads and governed writes | Production native OAuth status HTTP 200, configured=true; no saved account in the inspected workspaces. |
| Confluence | Spaces/pages, search, attachments and export | Production native OAuth status HTTP 200, configured=true; no saved account in the inspected workspaces. |
| PagerDuty | Services/on-call, incidents and governed incident updates | Production native OAuth status HTTP 200, configured=true; no saved account in the inspected workspaces. |
| Bitbucket | profile.get | Nango dev OAuth configuration exists; zero connections. Authenticated profile read NOT RUN. |
| DigitalOcean | account.get | Nango dev OAuth configuration exists; zero connections. Authenticated account read NOT RUN. |
| Sentry | organizations.list | Nango dev API-key configuration exists; zero connections. Fixed missing hostname input; authenticated organization read NOT RUN. |

Sentry's reviewed Nango template uses `https://${connectionConfig.hostname}/api`.
Gravitre now requires a hostname from its exact upstream allowlist: sentry.io,
us.sentry.io, eu.sentry.io or de.sentry.io. URLs, local addresses, arbitrary
hosts and suffix-spoofed domains are rejected before authorization. The existing
proxy path `/0/organizations/` correctly joins the template's `/api` base.
Bitbucket `/2.0/user` and DigitalOcean `/v2/account` match their root proxy bases.

Verification evidence:

- Nine-vendor connector/service regression: 120 passed, zero skipped.
- Follow-up input/auth-flow/business-read regression: 70 passed, zero skipped.
- Live native checks used `/api/connectors/oauth/{vendor}/status` on the Railway
  production backend; these prove app configuration presence, not valid user grants.
- Fresh Nango UI inventory showed zero connections for Linear, GitLab, Bitbucket,
  DigitalOcean and Sentry. Existing templates were not overwritten.
- A read-only connector inventory, including both vendor and legacy type fields,
  found no nondeleted accounts for these vendors in the same three owner/test
  workspaces used by the catalog audit. This is not an inventory of other tenants.

No provider action was fabricated or invoked without an account. No write was
performed against provider resources, and no agent permissions were expanded.
Bitbucket, DigitalOcean and Sentry currently offer the bounded read actions above;
the existence of their auth templates does not imply broader workflow support.
Account consent and a real scoped read remain required for end-to-end acceptance.

# Shared connector credential tenant scope

The canonical `get_decrypted_secret` and batched reader previously selected
credentials using connector ids without an org predicate. This draft makes the
authorized `org_id` a required keyword argument and filters both reads by it.
Missing scope returns no plaintext and makes no database request. No inference
from the secret row's own org, default org, or global service identity is used.

All 126 app callsites through the secret/OAuth/masking helpers now pass scope
from their existing authenticated route, tool context or background job. The
OAuth-token loader requires scope too, so refresh, revoke and connection-health
paths retain the caller's tenant. Masked/preloaded and legacy encrypted row
fallbacks require both the connector id and row org to match before use.

Adjacent direct paths are scoped too: webhook secret-header reads, OAuth token
deletion, and secret updates. A secret write requires the connector to exist in
the caller's org before encryption, then scopes both the existing-row lookup
and update. A foreign connector id cannot overwrite another org's stored key.

The isolated operator scripts were updated to pass their already declared
source/test org. They were not executed. This change does not authorize copying
credentials, sending messages, running provider actions or altering production.

New tests cover a foreign connector id, mixed-tenant bulk ids, absent scope,
masked/preloaded foreign rows, and a source inventory that rejects unscoped
helper calls. Existing mocks now require the org keyword; fixtures include the
real connector_secrets.org_id field. Focused CI precedes the full backend suite.

No migration or feature flag is needed. Production acceptance must verify
legitimate org credentials still work, a foreign connector reference cannot be
used, and refresh/revoke/background-sync paths use the correct org. This does
not complete MSP delegated access; explicit child membership remains required.

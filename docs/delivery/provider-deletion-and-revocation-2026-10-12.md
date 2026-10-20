# Provider deletion and revocation behaviour (2026-10-12)

Scope: PR #375, incremental deletion propagation for HubSpot, Zendesk, Confluence and
Notion, after the owner's release decision ("conditional go after remediation"). This page
says, for each provider, what we ingest, which upstream signal we act on, how "archived"
differs from "deleted", whether we can revoke the grant on disconnect, and what a customer
still has to do by hand.

## Switches: automatic live deletion stays off

| Setting | Default | Effect |
|---|---|---|
| `SOURCE_DELETION_PROPAGATION_ENABLED` | `false` | Off: syncs read no deletion signal and change nothing. Must be exactly `true` to turn on. |
| `SOURCE_PURGE_DRY_RUN` | `true` | Anything but an explicit `false` keeps both exclusion and removal a plan: an audit receipt (`source.documents_exclusion_planned`, `source.documents_removal_planned`) and no write. |
| `CONNECTOR_PROVIDER_REVOKE_ON_DISCONNECT` | `false` | Off: disconnect does not call any provider revoke endpoint. |
| `KNOWLEDGE_RETENTION_PRUNE_ENABLED` + org `sourceDataGovernance.retentionDays` | off | The separately authorised retention rule. It is the only path, besides confirmed deletion, explicit disconnect purge, or an explicit purge, that permanently removes an excluded document. |

The defaults are pinned by `backend/app/config.py` (`source_deletion_propagation_enabled:
bool = False`, `source_purge_dry_run: bool = True`), by
`scripts/railway_safety_vars.py`, and by the test
`test_defaults_keep_automatic_live_deletion_off`. Nothing in this PR turns a flag on.

## Rule: archived is not deleted

Upstream content in a state the provider can still undo (archived, trashed, soft-deleted,
recycle bin) is **excluded from retrieval**, not deleted:

* The active document version gets `is_active = false` and a
  `metadata.source_exclusion = {reason, signal, excluded_at}` marker. Chunks, embeddings
  and derived entity observations are kept.
* Every retrieval path already filters on `is_active`: the `rag_search` vector RPC
  (`d.is_active IS TRUE`), the BM25 keyword arm and the legacy keyword fallback
  (`rag_documents!inner(is_active)`), glossary extraction, and document listings.
* Queued or running ingest jobs for the record are failed with
  `error_code = 'source_excluded'`; the worker discards the version of such a job, so a job
  claimed before the exclusion cannot put the record back.
* When the record is live again (listed as current, or present on a by-id read), the
  latest excluded version is re-activated and the marker cleared
  (`source.documents_restored` receipt). A re-ingest of the record also activates a new
  version. Restore never activates a superseded version and never creates a second active
  version.

Permanent removal (`source.documents_removed`) needs **confirmed deletion**: an explicit
"deleted" status, or a by-id read that cannot mean "archived" (below, per provider). It
cascades to chunks and embeddings, fails queued jobs (`source_deleted`), drops their raw
payloads, and deletes derived observations.

Kept from the earlier review rounds, each still covered by tests:

* Absence is never proof: a record missing from a listing is never acted on by itself.
* Full-sweep reconcile (Notion) runs only after a provably complete listing.
* Safety cap: one pass removes at most max(5, 25% of the documents considered); above
  that it removes nothing and writes `source.documents_removal_refused`. Exclusions are
  reversible and do not count toward the cap.
* Org and source isolation: every read and write is filtered by `org_id` and `source_id`.
* Idempotent: excluding an excluded record, or removing a removed one, is a no-op with no
  new receipt.
* Retries: a listing or by-id error keeps the cursor or position where it was; the
  Confluence and HubSpot clients retry 429/5xx; an auth, permission or rate-limit error is
  never read as a deletion.
* Audit receipts for every pass that finds something: planned, excluded, removed,
  restored, refused.

## Per provider

### Confluence (Atlassian OAuth 2.0 3LO, REST v2)

* **Ingestion:** pages of configured spaces (`GET /spaces/{id}/pages`, which returns
  current and archived pages), body via `GET /pages/{id}?body-format=view`.
* **Signals read** (flag on): page `status` in the space listing; the space's trash
  (`GET /spaces/{id}/pages?status=trashed`); a rotating check by id
  (`GET /pages/{id}` with `status=current,archived,trashed,deleted`) of 25 indexed pages per
  sync.
* **Archived vs deleted:**
  * `archived`: still in the space and restorable by unarchiving. Excluded.
  * `trashed`: in the space trash, restorable by a space admin. Excluded.
  * `deleted` status, or 404 on the by-id read that asks for every status: purged from the
    trash, gone. Removed.
* **Caveat:** Confluence also answers 404 when the connecting user lost view permission on
  the page. We treat that as deletion: the content is no longer the connector's to serve.
  Customers who restrict a page and want it kept must reconnect with a user who can see
  it.
* **Revoke on disconnect:** not supported. Atlassian has no public endpoint for an OAuth
  app to revoke a user's 3LO grant.
* **Customer must do by hand:** remove the app from *Atlassian account settings, Connected
  apps* (each user who consented), or have a site admin remove it under *Administration,
  Apps*.

### HubSpot (OAuth, CRM v3)

* **Ingestion:** notes and emails, incremental by `hs_lastmodifieddate` through the search
  API.
* **Signals read** (flag on): the archived listing
  (`GET /crm/v3/objects/{notes|emails}?archived=true`, paged, up to 500 per run per type);
  a rotating check by id of 25 indexed records per sync.
* **Archived vs deleted:**
  * `archived: true` in the archived listing: the record is in the recycle bin and can be
    restored. Excluded.
  * By id, the plain read answers 404 for archived records too, so a 404 alone is not
    proof. The record is read again with `archived=true`: found means archived (excluded);
    404 on both reads means permanently deleted (recycle bin emptied, or a GDPR delete).
    Removed.
* **Revoke on disconnect:** supported (`DELETE /oauth/v1/refresh-tokens/{token}`) when
  `CONNECTOR_PROVIDER_REVOKE_ON_DISCONNECT=true`.
* **Customer must do by hand:** nothing extra once revoke is on; otherwise uninstall the app
  under *Settings, Integrations, Connected apps*.

### Zendesk (API token or OAuth, Support API v2)

* **Ingestion:** solved tickets, incremental by `updated_at` through the search API.
* **Signals read** (flag on): the deleted-tickets listing
  (`GET /deleted_tickets.json`, oldest deletion first, windowed); a rotating check by id
  (`GET /tickets/{id}.json`) of 25 indexed tickets per sync.
* **Archived vs deleted:**
  * In "Deleted tickets": soft-deleted, restorable by an admin for 30 days. Excluded.
  * 404 by id: Zendesk returns it for soft-deleted tickets as well as for tickets deleted
    for good, so it excludes. A ticket this pipeline excluded more than 30 days ago that
    still answers 404 has been scrubbed by Zendesk and can no longer be restored: only then
    is it removed. A ticket returned with `status: deleted` is excluded.
  * Zendesk "archived" tickets (closed tickets moved to the archive after 120 days) are
    still readable by id and are not touched.
* **Revoke on disconnect:** not supported by us. API tokens cannot be revoked by an app;
  Zendesk OAuth token revocation is not wired.
* **Customer must do by hand:** delete the API token under *Admin Center, Apps and
  integrations, Zendesk API*, or revoke the OAuth client's tokens under *Admin Center, OAuth
  clients*.

### Notion (public integration OAuth, API 2022-06-28)

* **Ingestion:** configured pages, and every page of configured databases
  (`POST /databases/{id}/query`), with block text.
* **Signals read** (flag on): the page object's `archived` / `in_trash` on every read;
  a full-sweep reconcile, after a provably complete database listing, that checks unseen
  indexed pages by id (`GET /pages/{id}`, up to 200 per run, rotating).
* **Archived vs deleted:**
  * `archived: true` or `in_trash: true`: the page is in Notion's trash and restorable
    (Notion empties the trash after 30 days). Excluded.
  * 404 `object_not_found` by id: the page was deleted for good, or is no longer shared with
    the integration. Removed, under the safety cap.
  * A page that still exists but is no longer under a configured target is out of scope
    and kept for an explicit purge.
* **Revoke on disconnect:** not supported. Notion has no token revocation endpoint for
  public integrations.
* **Customer must do by hand:** remove the integration under *Settings, Connections* in the
  Notion workspace (a workspace owner can remove it for everyone).

## Revoke support across connectors

| Provider | Provider-side revoke on disconnect (implemented in Gravitre) | What the customer does |
|---|---|---|
| Google (Gmail, Drive, Docs, Sheets, Calendar, Analytics, Search Console, Ads) | Yes (skipped while another Google connector in the org shares the grant) | Nothing, or *Google Account, Security, Third-party connections* |
| HubSpot | Yes | Nothing, or uninstall under *Connected apps* |
| Slack | Yes | Nothing, or remove the app from the workspace |
| Salesforce | Yes | Nothing, or *Setup, Connected Apps OAuth Usage, Revoke* |
| Microsoft 365 | **No** (the Microsoft identity platform offers no endpoint for an app to revoke its own delegated grant) | Remove the app under *My Apps / myaccount.microsoft.com, Permissions*, or an admin removes the enterprise application consent in Entra ID |
| Notion | **No** | Remove the integration under *Settings, Connections* |
| Zendesk | **No** | Delete the API token or revoke the OAuth client's tokens in *Admin Center* |
| Atlassian (Confluence, Jira) | **No** | *Atlassian account settings, Connected apps*, or site admin removes the app |
| Intercom | **No** | Uninstall the app under *Settings, Integrations, Installed apps* |
| Workday | **No** | A Workday admin deletes the API client / refresh token under *View API Clients* |

In every case, disconnecting in Gravitre stops our use of the token immediately (our copy is
dropped) and emits `source.disconnected`, whose handler purges the connector's derived data
(dry-run until `SOURCE_PURGE_DRY_RUN=false`). Unsupported revocation only means the grant
stays valid at the provider until it expires or the customer removes it.

## Evidence

* Offline, through the real HTTP client layer:
  `backend/tests/services/test_provider_deletion_http_contracts.py` replays provider
  responses shaped after each published API reference
  (`backend/tests/services/fixtures/provider_deletion/*.json`) through `httpx.MockTransport`.
  The connector code under test is unmodified: URLs, query parameters, headers, retry on
  429, error envelopes and JSON decoding all run for real.
* Semantics and safety properties: `test_archived_exclusion.py`,
  `test_incremental_deletion_propagation.py`, `test_deletion_propagation_safety.py`.
* **Not yet done, needs the owner:** `backend/tests/integration/test_provider_deletion_sandbox.py`
  checks the same verdicts against real sandbox accounts. It is opt-in
  (`GRAVITRE_PROVIDER_SANDBOX_TESTS=1` plus `SANDBOX_*` credentials and record ids),
  read-only, refuses production runtimes, and fails, rather than skipping, on any account
  that does not identify as a sandbox. It has not been run: no sandbox credentials are
  available to the agent.

## Before acceptance

1. Run the sandbox module against owner-provisioned Confluence, HubSpot, Zendesk and
   Notion sandboxes, with one record per state.
2. Turn `SOURCE_DELETION_PROPAGATION_ENABLED=true` in staging with `SOURCE_PURGE_DRY_RUN`
   left `true`; review the `source.documents_exclusion_planned` and
   `source.documents_removal_planned` receipts.
3. Only after that review, and the owner's explicit acceptance, set
   `SOURCE_PURGE_DRY_RUN=false` anywhere.

# "Invalid parameters for this Hubspot action (Search deals via hubspot API)"

Status: **root-caused, fixed, awaiting live production proof**
Found: 2026-09-01, during verification of the fabricated-destructive-write fix.

## The report

One run in four of an ordinary read question — "Show me the most recent deals in
our HubSpot pipeline with their amounts and close dates." — returned
*"Invalid parameters for this Hubspot action (Search deals via hubspot API)"*
instead of the deals table. It was logged as intermittent, on the assumption
that a 1-in-4 failure rate implied a race, a timing issue, or a flaky upstream.

## It was never intermittent

`audit_events` over three days, 12 HubSpot deal invocations:

| Outcome | Action taken | Detail |
| --- | --- | --- |
| 8 succeeded | `hubspot.deals.list` | 824 ms, returns the table |
| 4 failed | `hubspot.deals.search` | `validation_error`: "hubspot.deals.search requires filter_groups array" |

Every failure is the same error, and it partitions perfectly by which action ran.
Nothing is racing and nothing upstream is flaky: the model picks one of two
plausible tools for the same request, one works and one refuses. The
"intermittence" was tool selection, sampled from outside.

Evidence: `docs/delivery/hubspot-deals-search-validation-probe.json`

## Root cause: the catalog advertises a contract the executor refuses

`backend/app/connectors/action_catalog/action_parameters.py` advertises
`hubspot.deals.search` to the model as:

```python
"hubspot.deals.search": {
    "properties": {
        "query": {"type": "string", "description": "Optional keywords to build a dealname CONTAINS filter."},
        "filter_groups": {"type": "array", "items": {"type": "object"}},
        "limit": {"type": "integer", "default": 25},
    },
    "required": [],          # nothing is required
},
```

So the schema states plainly that no field is required, and that `query` alone is
enough because the executor will build the filter from it.

The executor did neither. `_exec_hubspot_deals_search` ignored `query`
completely and hard-failed unless `filter_groups` was both present and
non-empty. A model following the advertised schema exactly — which is what it
did — could not produce a call that passed.

This is not a race. It is a **deterministic failure of every criteria-less or
query-only call**, and the model was never shown the rule it was being held to.

### Class-level, not one action

All four HubSpot search actions have the identical disagreement:

| Action | Advertises `required` | Advertises `query` | Executor honoured `query` | Executor allowed no criteria |
| --- | --- | --- | --- | --- |
| `hubspot.deals.search` | `[]` | yes | no | no |
| `hubspot.contacts.search` | `[]` | yes | no | only via `list_all`, which the schema never advertises |
| `hubspot.companies.search` | `[]` | yes | no | no |
| `hubspot.tickets.search` | `[]` | yes | no | no |

`contacts.search` already had the right instinct — a `list_all` branch serving
unfiltered requests from the list endpoint — but that parameter appears nowhere
in the advertised schema, so no model could know to send it.

## Why the fix is not "relax the validation"

The obvious patch is to send `filterGroups: []` to HubSpot and let the vendor
sort it out. That was checked against the vendor's published contract rather
than assumed, and the check does not support it:

HubSpot's own OpenAPI spec (`PublicObjectSearchRequest`, version 2026-03, for
Deals, Contacts, Companies and Tickets alike) lists `required: [after,
filterGroups, limit, properties, sorts]`. Two things follow:

1. `filterGroups` is nominally required, so quietly dropping our check is not
   obviously safe.
2. That same list marks `after` and `sorts` required, which they demonstrably are
   not in practice — so the spec's `required` is a codegen artifact and cannot be
   read as authoritative either way. It is also silent on whether an *empty*
   array is accepted.

The honest position: **the vendor's behaviour for an empty `filterGroups` is
unproven**, and a fix must not depend on it. Local verification could not settle
it because the local environment has no HubSpot OAuth client credentials, so no
raw vendor call can be made from here.

Evidence: `docs/delivery/hubspot-search-vendor-contract.json`

## The fix

Make the executors honour the contract they advertise, without relying on any
unproven vendor behaviour. One shared resolver, so the four actions cannot
drift apart again:

- `filter_groups` supplied → passed to the vendor unchanged (unchanged behaviour).
- `query` supplied → build the `CONTAINS_TOKEN` filter the schema promises, on
  the properties that make sense per object (`dealname`; `subject`;
  `name`/`domain`; `email`/`firstname`/`lastname`/`company` for contacts).
- no criteria at all → serve it from the vendor's GET list endpoint, because an
  unfiltered search *is* a list. `list_deals` already does this at 824 ms and is
  the proven-working path from the table above.

We never send an empty `filterGroups` to HubSpot, so the unresolved vendor
question stays out of the critical path.

Files:
- `backend/app/services/tool_service.py` — `_resolve_hubspot_search`,
  `_hubspot_text_filter_groups`, and the four executors.
- `backend/app/connectors/hubspot.py` — added `list_companies`, `list_tickets`
  (read-only GETs) so companies and tickets have the same fallback deals and
  contacts already had.

## Proof

- 21 tests, `backend/tests/services/test_hubspot_search_honors_advertised_schema.py`,
  covering all four actions in three shapes each plus the resolver's precedence
  rules, and pinning the advertised schema itself so a future change to
  `required` breaks the test rather than production.
- Mutation-proven, 4/4 caught
  (`backend/scripts/scratch_mutate_hubspot_search_guards.py`): reintroducing the
  original dead-end, dropping `query` support, inverting filter precedence, and
  collapsing contacts' free-text properties each turn the suite red.
- Pre-existing failures in `tests/e2e/test_chat_e2e_scenarios.py`
  (`hubspot_search_acme_contacts`, `hubspot_deal_create_with_approval`) were
  confirmed unrelated: they fail identically with these changes stashed. They
  need a real database and real API keys.
- **Live production proof: pending.** Three green mutation-proven suites
  accompanied three live failures earlier in this same session, so the tests
  above are not the evidence. The claim is closed only by a production run
  showing successful `hubspot.deals.search` invocations with no
  `validation_error`.

## Broader item, deliberately not fixed here

A tool returning `validation_error` is surfaced to the user as a dead end; the
ReAct loop does not attempt a repaired retry. That would have made this
self-healing regardless of the contract bug, and it is the general safety net for
"model called a tool with arguments the executor rejects". It is a genuinely
larger change than this fix and is recorded here rather than rushed in.

Related: `docs/delivery/readonly-destructive-proposal.md` — the same
model-tool-selection variability, in the destructive direction.

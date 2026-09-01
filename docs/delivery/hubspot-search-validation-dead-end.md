# "Invalid parameters for this Hubspot action (Search deals via hubspot API)"

Status: **two distinct causes behind one message. Cause (a) fixed and
live-proven at 77c54964. Cause (b) found by that same live run, fixed, awaiting
its own live proof.**
Found: 2026-09-01, during verification of the fabricated-destructive-write fix.

One symptom string, two unrelated faults:

| | Trigger | Nature | Status |
| --- | --- | --- | --- |
| (a) | `hubspot.deals.search` called with no `filter_groups` | deterministic; the advertised schema invited a call the executor refused | fixed, live-proven 9/9 at 77c54964 |
| (b) | any transport/timeout/5xx failure on any HubSpot action | genuinely intermittent; mislabelled `validation_error` | fixed, live proof pending |

Cause (b) is why the report looked intermittent even after (a) is explained. It
was found only because the live proof for (a) checked the audit trail rather than
just the absence of the error string.

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
### Live production proof — cause (a): PASS

`scripts/verify-hubspot-search-dead-end-live.py` against deployed tip
**77c5496482531ab164fe9e54559b5cf99ed8e801**, 10 turns, org
`f07e57c0-1501-4000-8000-c04e57a00001`
(`docs/delivery/hubspot-search-dead-end-live.json`):

- **9 `hubspot.deals.search` invocations, all completed, zero `validation_error`.**
- 10/10 turns answered with real deal content.
- The proof deliberately required a *completed* `deals.search`, not merely the
  absence of failures: a run where the model happened to pick `deals.list` every
  time would have shown zero errors while proving nothing.

Before the fix the same action failed 4 out of 4 times it was chosen. It now
succeeds every time it is chosen, including the criteria-less shape.

## Cause (b): a transport failure reported as bad parameters

The live run above surfaced a second, unrelated fault. One invocation recorded:

```
tool.invoke.failed   hubspot.deals.list
error      = "[Errno 11] Resource temporarily unavailable"
error_code = "validation_error"
```

which rendered to the user as *"Invalid parameters for this Hubspot action (List
deals via hubspot API). Check required fields and try again."* — the same
sentence as cause (a), from a completely different fault.

`_handle_hubspot_error` classified only 429 and 401/403, and mapped **everything
else** to `ToolValidationError`:

```python
if exc.status_code == 429:      return ToolRateLimitedError(str(exc))
if exc.status_code in {401,403}: return ToolAuthExpiredError(str(exc))
return ToolValidationError(str(exc))          # timeouts, 5xx, socket errors…
```

`_request` raises `HubSpotAPIError(str(exc))` with **no status code** for
transport errors and for `"HubSpot API timeout"`, so both landed in that final
line. Consequences: the user is told to fix parameters that were never wrong,
given advice that cannot help, and a retryable fault is presented as a permanent
one. `"HubSpot API timeout"` was reported as invalid parameters too.

Fixed by classifying on what actually happened — 4xx is the caller's input, 5xx
is HubSpot failing, no status code is a timeout or transport fault — reusing the
`connector_timeout` and generic `tool_error` templates that already existed.

Proof: `backend/tests/services/test_hubspot_error_classification.py`, 13 tests
pinning each failure kind, and 3 further mutations in the same mutation script
(7/7 caught overall). **Live proof for (b) still pending** — it needs a real
transport failure to recur in production, which cannot be forced on demand;
what can be verified live is that no `validation_error` is emitted for a
non-4xx cause.

### Note on the reply that carried this error

The same reply also said *"Done — List deals … HubSpot now has this record"*
directly after the error text, for a read action that failed. Two problems in
one message — a completion claim over a failure, and "has this record" for a
list. Recorded here; not fixed in this pass.

## Broader item, deliberately not fixed here

A tool returning `validation_error` is surfaced to the user as a dead end; the
ReAct loop does not attempt a repaired retry. That would have made this
self-healing regardless of the contract bug, and it is the general safety net for
"model called a tool with arguments the executor rejects". It is a genuinely
larger change than this fix and is recorded here rather than rushed in.

Related: `docs/delivery/readonly-destructive-proposal.md` — the same
model-tool-selection variability, in the destructive direction.

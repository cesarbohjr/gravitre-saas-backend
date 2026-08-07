# Phase 3 — Catalog-wide verified completion (F6 generalized)

## Bar

Every mutating catalog write declares how success is independently confirmed.
Follow-up settle reuses F6 retry logic and must not block chat TTFT.

## Counts (seed tip)

| Metric | Value |
|--------|------:|
| Mutating actions | **344** |
| Declared success checks | **344** (100%) |
| `follow_up_membership` (F6) | 3 |
| `follow_up_entity_get` (sibling GET) | 70 |
| Honest `accepted_async` (no sibling GET yet) | 271 |

Catalog total ActionSpecs ≈ 691; Phase 3 scope is the mutating subset (write authority), not reads.

## Mechanisms

- Catalog: `backend/app/connectors/action_catalog/data/success_verification_catalog.json`
- Generator: `backend/scripts/generate_success_verification_catalog.py`
- Runtime: `backend/app/services/write_success_verification.py`
- CI: `test_every_mutating_action_has_success_verification` in schema-standard lint
- Chat: finalize uses **inline-only** population proof; F6 settle scheduled via
  `asyncio.create_task` / background thread **after** Module A finalize

## Examples

| Action | Mode | Confirm via |
|--------|------|-------------|
| `apollo.lists.add` | follow_up_membership | `apollo.lists.list` |
| `hubspot.lists.add_contact` | follow_up_membership | `hubspot.lists.get` |
| `hubspot.contacts.create` | follow_up_entity_get | `hubspot.contacts.get` |
| `salesforce.leads.create` | follow_up_entity_get | `salesforce.leads.get` |
| `mailchimp.members.add` | follow_up_entity_get | `mailchimp.members.get` |
| `hubspot.notes.create` | accepted_async | honest — no sibling GET in catalog |

## TTFT

Settle sleeps are not on the finalize hot path. Unit proof:
`test_schedule_write_success_verification_returns_immediately`.
Live F6 script remains the membership settle proof (may take tens of seconds
**after** the user-visible response).

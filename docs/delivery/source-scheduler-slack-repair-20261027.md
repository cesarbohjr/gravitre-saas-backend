# Source scheduler, audit attribution and Slack retry repair

The data-source health scheduler was polling two connector-ingested HubSpot
knowledge sources with no standalone encrypted connection configuration, and a
static manual source. Their recorded failures were respectively `Linked
connector ID is required` and `Unknown data source type: manual`. These are
ownership errors, not evidence that the HubSpot integration failed.

The scheduler now excludes unsupported/static records and connector-ingested
knowledge records owned by the existing ingestion scheduler. External connection
checks retain their existing behavior and never claim data ingestion. Successful
checks clear stale error metadata; mutations include the organization predicate
and explicitly foreign source bindings are rejected before any mutation.

Scheduled events now use a current source creator or organization owner/admin
for UUID/FK-compatible responsibility attribution. Audit metadata explicitly
identifies `executionActor=system`; it does not claim that the human executed the
job. A missing responsible member prevents an unauditable check and emits an
explicit error. No fabricated UUID or weakening of audit schema is introduced.

Slack rejects the isolated smoke connector's credential with `invalid_auth`.
Repeated checks of the same rejected token are now bounded by a five-minute
process-local negative cache. Only fixed terminal authentication errors are
cached. A replacement token is checked immediately. HTTP/network/rate-limit or
malformed-response failures return temporary unavailability rather than false
credential expiry. No token, fingerprint or provider body is logged by this change.
The credential itself still requires owner reconnection; retry handling does not
restore authorization or prove successful Slack notification delivery.

## Executed evidence

- 36 targeted scheduler, Slack, connector health and audit-redaction tests passed
  with the normal backend fixtures and the offline network guard. One existing
  Starlette deprecation warning. Syntax compilation and diff checks passed.
- On production, the existing standalone scheduler flag `syncEnabled=false` was
  set only on the three identified misrouted records. Their stored error states
  were preserved, not relabeled healthy. Their owning ingestion/static paths
  remain unchanged. Readback confirmed all three flags.
- All three production repairs were recorded atomically in `audit_events` at
  2026-10-27 19:32:33 UTC. Event IDs:
  `61a3699e-c2c0-4aed-9e8c-5995619e9ca3`,
  `2130a2cc-cf66-4be7-ade0-da1496d919a5`,
  `0b705047-3716-4ae4-bf3c-cbca09e5f1eb`.
- Isolated evaluator deployment `cbbb05b7-a2d6-43a0-b537-4a4c269abd0d`
  recorded Anthropic inference PASS (HTTP 200, nonempty response) and OpenAI
  FAIL (HTTP 401). These results are separate from this operational repair.

This report does not establish deployment of the code changes, green CI for their
commit, successful ingestion, restored Slack authorization, the 520 generated
evaluation pairs or live Pipecat certification. Those gates remain independent.

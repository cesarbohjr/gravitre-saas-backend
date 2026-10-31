# Phase 2: memory and session continuity

This increment reuses CognitiveTurnKernel, conversation task_state/history,
agent_memories, organization_members, and organizations.settings. No database
migration, parallel memory store, automatic conversation extraction, or new
customer-facing toggle is introduced. Implementation remains on the Phase 2
branch; no organization policy, deployment, or production data was changed.

## Current-session continuity

Authenticated conversation requests supply their existing scoped history and
task state. At most three recent user turns (500 characters each, selected from
the last twelve messages) and the status of an unresolved pending task enter an
ephemeral `session_continuity_section`. Explicit foreign organization, actor or
conversation bindings are excluded. Missing actor/conversation identity yields
no continuity section. The caller must continue to authenticate and load history
through the existing conversation-access checks; this helper is not a replacement
for ingress authorization.

The section treats history as untrusted conversation data, gives the current
message and newest corrections precedence, and explicitly denies authorization
from old confirmations. Assistant-generated claims and action parameters are not
copied. Only counts and a pending-status boolean enter stage diagnostics. The
section is consumed by the existing context compiler, unified prompt assembly,
and agent task prompt assembly; spoken conversational depth retains continuity
without turning heavy cross-conversation recall back on.

## Governed durable memory rollout

`DIALOGUE_MEMORY_GOVERNANCE_V1` defaults to false. This preserves the existing
memory system until a deliberate rollout; it is not a claim that all legacy
platform memory paths already follow the new policy. When enabled, it gates
the canonical kernel's RECALL and typed-memory promotion in LEARN. Other
retrieval, entity, training and memory-management paths retain their existing
authorization contracts and are not silently reconfigured by this increment.

An authorized settings manager configures the existing organization settings
object through `/api/settings` (PATCH requires `org_settings_billing` capability):

```json
{
  "dialogueMemory": {
    "recallEnabled": true,
    "learnEnabled": false,
    "actorIds": ["authorized-member-id"],
    "retentionDays": 30
  }
}
```

This is an illustrative policy, not a configured setting. Omit `actorIds` to
allow current organization members; an explicit empty list denies everyone.
Recall and learning require separate literal boolean opt-ins. Missing identity,
membership, policy, malformed values or database failures deny durable access.
Do not submit this fragment alone to the generic PATCH endpoint: that endpoint
replaces settings, so preserve the organization's other settings. The existing
settings audit records the update. Service jobs without an actor fail closed.

Policy is not cached. Recall rechecks it after concurrent stores finish; LEARN
reads it afresh before typed-memory promotion. Outcome telemetry remains under
its existing rules and is not conflated with permission to save memories.

Search hits are rehydrated from current, tenant-scoped agent_memories records.
Deleted, inactive, superseded, expired, future-invalid, malformed-validity,
retention-expired, foreign-tenant/agent, and foreign private-owner records are
excluded. Connector revocation uses the existing liveness helper and fails
closed on lookup errors. Fresh authoritative content replaces stale search text.
Hits without verifiable memory IDs (including graph/ledger summaries) are omitted
in governed mode; this is intentionally narrower than legacy recall. Retention
is a read-time cutoff based on record creation, not a new physical deletion job.
Existing deletion/pruning APIs and temporal supersession remain authoritative.
Metadata lookup failures are reported as degraded governance, not a clean zero.

## Verification boundary

Tests exercise policy/membership denial, absent and malformed policy, independent
learn consent, mid-retrieval revocation, authoritative replacement, deletion,
expiry, retention, supersession, private ownership, source revocation, session
corrections and limits, text/spoken propagation, disabled recall, and private
diagnostics. Existing temporal-memory, source-liveness, kernel, compiler, unified
reasoning and spoken-write regressions are included. Tests use fake database
responses; production RLS, live model quality and real-device voice acceptance
remain NOT RUN. Those require separate evidence before release certification.

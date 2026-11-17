# Persisted outcomes, outbox delivery and crash recovery

This is a bounded repair/evidence record under the existing 43-finding register,
not a new roadmap or release certificate. Original IDs, owners, order and
closure gates remain authoritative. No workflow, migration, provider call,
runtime flag or deployment is added by this batch.

## Confirmed defects and resulting behavior

- `execution_outcome._persist_run` wrote a terminal status before verification
  metadata, then marked notification delivery/finalization before those channels
  ran. A crash or channel failure could suppress remaining delivery. Output and
  rollup proof now persist before the terminal/outbox boundary. Core run, audit,
  notification and learning acknowledgements are checkpointed after success.
  A fresh finalizer resumes only core channels lacking durable acknowledgements.
- A late caller could return success over an already persisted cancellation or
  failure. Conflicting definite terminals now retain the persisted status.
  Promoting an uncertain outcome to success requires attributable verification.
- Execution-edge telemetry could throw before consumer dispatch or after its
  effect committed, blocking delivery or scheduling a duplicate retry. The three
  telemetry boundaries now return false when the log sink is unavailable.
- Stale-run classification treated a missing/retired invoke-tool action as safe
  to retry. Such steps now require review/reconciliation. Known reads retain the
  existing bounded recovery behavior; no provider work is re-executed here.

Audit acknowledgement means canonical `audit_logs` storage. Dual-write attempts to
`audit_events` remain in place, and gaps retain their existing diagnostics. Optional
SIEM scheduling failure no longer invalidates a committed canonical audit. Notification
acknowledgements require the returned inbox-row ID; learning requires returned insert
rows. Positive test collaborators now return these actual success shapes; missing
acknowledgements are covered explicitly.

## Evidence

- **114 primary focused local checks pass**, covering finalization/effect gates, retry
  receipts, lifecycle fallback contracts, relay, telemetry and stale recovery.
  The lean local runs use `--confcutdir=tests/services` and explicit dummy test
  settings; they do not certify the repository's complete global test fixtures.
- **20 selected regressions fail on pre-repair source**: 12 receipt/terminal-proof,
  six telemetry/consumer and two unknown-action recovery cases.
- Existing PostgreSQL acceptance files now include **five new executable cases**:
  three partial-channel retries with independently queried SQL receipts, an
  actual finalizer subprocess exit after audit acknowledgement followed by
  restart, and a real SQL consumer commit followed by telemetry failure.
  The receipt fixture also installs a database trigger rejecting a terminal
  transition before output persistence. Production repository/mirror/outbox
  code remains real; external channels use explicitly synthetic SQL stand-ins.
- Local PostgreSQL execution is **NOT RUN**: process startup cannot bind its
  Unix socket in this runtime. The existing canonical QA acceptance lane already
  selects both modified PostgreSQL files and requires server availability.

Neighboring workflow recovery/audit-redaction checks also pass (15 cases); the
existing action-lifecycle and outcome-ownership suites pass separately (77 cases).
The combined focused local total is **206 passing cases**.

## Scope and remaining gates

Versioned receipts are restart checkpoints, not concurrent exactly-once claims.
The existing repository parameter merge remains read-modify-write. Consumers
still need idempotency for a crash between a committed effect and its receipt;
concurrent finalization needs a separate fenced/atomic claim. Optional fanout
remains best effort. Historical skip markers retain compatibility but are no
longer reported as proof that audit/learning channels succeeded. Legacy rows
are not silently backfilled or redelivered by this repair.

ECO-010/ECO-014, P27-03 and DEC-006/007/019 receive bounded persistence/delivery
repairs; P27-05/P27-08 receive bounded recovery repairs. Exact-head CI, real
provider/consumer readback, cross-surface concurrency and cancellation, deployed
rollback and owner approval remain open. No finding is closed by this record.


## Atomic parameter follow-up (2026-11-16)

The previous `c10601b360c1b0df36a1931d432d2215a1cbe0cd` checkpoint passed all ten
CI lanes. QA12 run [43830418575](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/43830418575)
passed 59 real PostgreSQL cases, including the five new recovery cases, alongside
321 runtime guards and 43 routing/context contracts. This is bounded evidence;
no full finding is certified by those results.

The shared repository parameter merge now calls `merge_workflow_run_parameters`.
The function locks the run before reading and merging top-level keys, preserving
disjoint concurrent patches. It retains historical object/string normalization
and shallow replacement semantics. Missing runs, invalid patches, missing RPCs
and malformed acknowledgements fail closed. The existing contract mirror is
still invoked after a successful merge; parameter data remains canonical in
`workflow_runs`. This does not certify mirror concurrency for lifecycle updates.

This follow-up adds **11 PostgreSQL cases** to the existing selected acceptance
file: a deterministic 16-writer lock contention case, six legacy normalization
cases, three invalid-patch cases, and a missing-run/role-boundary/shallow-merge
case. The narrow psycopg transport invokes the actual SQL function. **67 focused
local checks pass**; seven new fail-closed cases fail on the pre-repair method.
Actual PostgreSQL validation awaits this revision's existing QA12 lane; local
socket restrictions are not treated as a passing or skipped database gate.

The function-only migration is additive, SECURITY INVOKER, and callable only by
`service_role` (PUBLIC/anon/authenticated execution revoked). Apply it **before**
activating the new backend. No hosted migration has been applied. For rollback,
restore the prior backend first and leave the additive function while newer
workers drain. Hosted migration/advisor checks, deployed rollback and owner
acceptance remain pending.

Remaining work under the same register/owners: atomically arbitrate terminal
status with proof, merge fanout acknowledgements monotonically, and make core
consumer effects idempotent across concurrent finalizers and the effect-to-receipt
crash gap. This patch does not claim any of those gates or close a finding.


## Atomic terminal and monotonic receipt follow-up (2026-11-16)

The previous `bd99007274f4a34ed05cabea380d80f20accb19a` atomic-parameter
checkpoint passed actual PostgreSQL acceptance: [QA12 job 133432648793](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/43905289807/job/133432648793)
reported **321 runtime guards, 43 routing/context and 70 real PostgreSQL cases**.
That proves the 16-writer parameter merge and its database boundaries at that
revision; full backend CI remains separate.

The canonical finalizer now calls `persist_workflow_run_outcome`. A tenant-scoped
row lock arbitrates the proof and terminal transition in one transaction. A
conflicting definite terminal wins without any caller proof write. Uncertain
promotion still requires the canonical service's attributed verification. A
status/outbox constraint failure rolls back the proof. Same-status retries retain
the first committed proof, actor, error and completion timestamp. The finalizer
uses that canonical proof/actor and performs work-object attribution only after
successful arbitration. New attribution references use the atomic parameter
merge. A rejected or failed persistence transaction suppresses all downstream
channels; failed completion persistence returns verification_inconclusive.

`checkpoint_workflow_run_outcome` merges same-status channel acknowledgements
with boolean OR under the row lock. A stale snapshot cannot erase an acknowledged
channel or finalization request. Completion derives from the merged required
channels. An actorless retry cannot weaken actor-required delivery. A new outcome
status resets the prior status's receipts; version-one same-status receipts are
preserved when upgrading to the new terminal writer. These are durable receipt
semantics, **not** an exclusive delivery claim or exactly-once external delivery.

**193 focused local checks pass**: 130 outcome/lifecycle/ownership and 63 neighboring
workflow/approval/recovery checks. Two negative finalizer regressions fail against
the previous finalizer. Five new unit regressions cover late cancellation,
failed persistence, canonical retry proof/actor, stale receipts and stale-status
checkpoint rejection. Ten new real PostgreSQL cases extend the existing selected
acceptance file: competing terminals, transaction rollback, stable same-status
proof/actor/timestamp, verified uncertain promotion, concurrent acknowledgements,
actorless retries/stale status, two tenant/role boundaries, and two actual-finalizer
negative journeys. Actual database validation awaits this revision's QA12 job;
unit transports do not certify SQL locking or rollback.

Both additive function migrations must precede backend activation. Both functions
are SECURITY INVOKER; PUBLIC/anon/authenticated execution is revoked and service_role
execution granted. No hosted migration or deployment was performed. Roll back the
backend before removing any function; leave additive functions for workers to drain.

Remaining gates under the original owners: core-channel effect idempotency across
concurrent finalizers and effect-to-receipt process death; optional/legacy fanout;
generic lifecycle-writer/contract-mirror races; full Chat/Agent/provider readback;
deployed rollback and owner acceptance. All 43 findings remain open.


## Core delivery idempotency follow-up (2026-11-16)

The prior terminal/receipt checkpoint `bfd359c55bd7453781418357b09d772344e66302`
passed [QA12 job 133441212071](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/43907748123/job/133441212071):
**321 runtime guards, 43 routing/context and 80 real PostgreSQL cases**, including
the ten new transaction/race cases. This is bounded gate evidence, not a finding
or release certificate.

Canonical persisted-run finalization now derives stable UUIDs from tenant, run,
terminal status and channel. Audit dual-writes, inbox notifications and learning
rows insert with these identities. They never replace existing effects. Only a
unique-key violation can trigger duplicate readback; the exact ID and tenant plus
channel context must match before acknowledgement. Other-key conflicts, missing
rows, wrong tenant/context and ambiguous writes are not acknowledged. A retry
with the same ID can recover an already committed but unacknowledged effect.

Duplicate inbox acknowledgement returns the durable ID without repeating email,
Slack, live bell or activity fanout and without resetting read/archive flags.
Duplicate audit rows do not repeat optional SIEM scheduling. Existing callers
without a delivery ID retain their previous insert behavior. Canonical audit_logs
acknowledgement and secondary audit_events diagnostics remain distinct.

**209 focused local checks pass** (145 outcome/delivery/lifecycle/ownership and
64 workflow/approval/recovery/audit). Four new PostgreSQL cases extend the existing
acceptance file: three actual finalizer subprocess deaths, each after a real core
channel commits and before its receipt, followed by restart with one row per core
store; and four simultaneous actual finalizers with one row per core store. Core
SQL writers are real; external/preference/SIEM channels are disabled explicitly.
Current-head database acceptance is pending. No new workflow or migration is
needed for delivery IDs; existing UUID primary keys enforce uniqueness.

This applies to effects written with stable delivery identities. Historical
unkeyed effects still need reconciliation; no automatic backfill or historical
exactly-once certificate is claimed. Optional external delivery remains best
effort: a crash after inbox insertion can leave an optional channel unattempted,
and duplicate core delivery does not replay it. Core idempotency does not prove
provider effect idempotency, generic lifecycle/mirror fencing, deployed migration
or rollback, full Chat/Agent parity or owner acceptance. All 43 findings stay open.


## Atomic projection follow-up (2026-11-16)

The prior core-delivery checkpoint `cbc086906f1617b04ca48fc97dbeeb729bbbfa83`
passed [QA12 job 133446690582](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/43909317615/job/133446690582):
**321 runtime guards, 43 routing/context and 84 real PostgreSQL cases**, including
all four actual-writer commit-before-receipt/concurrency cases. Full CI and
per-finding live/owner gates remain separate.

ECO-014 / DEC-007 / DEC-019 now receive a bounded projection repair. The old
application helper read a run and its steps, then upserted snapshots in separate
requests, allowing stale writes and partial mirrors. `refresh_workflow_run_projection`
now takes a canonical source-row lock before reading and writing both intentional
projections in one transaction. The application passes only run identity, never
an old status or snapshot. Unsupported source status, mismatched projection
organization or step parent rejects the entire refresh. The helper returns an
explicit boolean acknowledgement and never falls back to client upserts.

The canonical terminal SQL mutation invokes this refresh inside its transaction,
including same-status retries, so projection failure rolls back proof, terminal
status and outbox emission. The redundant post-commit application refresh on this
path is removed. Other nonterminal repository callers retain their existing
separate source mutation / refresh boundary and logged failures; this is not a
full generic-writer atomicity or live-consumer certificate.

The projection preserves unrelated consumer metadata, clears removed source
input/output snapshots, uses production `text[]` step logs and truncates duration
milliseconds like the prior Python helper. The disposable fixture previously
used `jsonb` for contract logs; it now matches the production schema. Production
workflow_runs historically lacks started_at, so refresh reads that field only
when present and otherwise uses created_at for the displayed start.

**216 focused local checks pass** (145 outcome/delivery/lifecycle/ownership and
71 workflow/approval/recovery/audit/projection boundary). **25 new PostgreSQL cases**
extend the existing acceptance file: 17 run-status translations, a deterministic
late-writer source lock, log/snapshot/metadata semantics, projection-induced
terminal rollback, three tenant/parent conflicts, missing-run/status/privilege
fences, and the source schema without started_at. Actual database validation for
this revision remains pending; local unit transports do not prove SQL execution.

Apply the additive projection function and replacement terminal function after
the prior parameter/outcome migrations and before backend activation. The new
function is SECURITY INVOKER with PUBLIC/anon/authenticated execution revoked;
service_role alone receives execution. No hosted migration, backfill, deletion,
deployment or storage retirement was performed. Rollback must retain the refresh
function while any terminal function/worker calls it. All 43 findings stay open.


## Projection negative-fixture correction and DEC-017 caller repair

The projection checkpoint `f941dd725dec15793283cd550dec40734693caf2` passed
321 runtime guards and 43 routing/context checks. Its [PostgreSQL job 133457389819](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/43912323133/job/133457389819)
reported **107 passes and two failures**, both new step-conflict fixtures that
updated nonexistent target rows. `create_step` creates canonical source data;
these fixtures must refresh before corrupting the projection. They now explicitly
refresh and assert a target row exists before injecting either wrong tenant or
wrong parent. The metadata test likewise seeds its target before injecting legacy
metadata. The original rejection/rollback assertions remain unchanged. No passing
database gate is claimed until the corrected exact-head acceptance runs.

A separate DEC-017 caller defect remained after the voice-origin repair: the
general backend proxy chose localhost in production without FASTAPI_BASE_URL,
workflow schema sync silently skipped, and authenticated run/step controls returned
configuration 503s. These callers now reuse the existing canonical backend resolver
in production. Development fallback and opt-in behavior remain explicit. No runtime
configuration, DNS, deployment or provider mutation was performed.

**12 request-level tests pass locally**, using actual NextRequest/NextResponse and
a controlled fetch upstream. **Four fail against previous source**, reproducing
all four affected production behaviors. They exercise default/alias/private/local
origins, body and tenant/auth header forwarding, missing-auth rejection before
dispatch, and development no-dispatch branches. The new test is under the standard
`__tests__` glob; the older lib voice audit file is outside that default glob and
is not counted as executed evidence. DEC-017's regression candidate now points to
the collected test. Targeted strict TypeScript checking passed; full exact-head web CI remains separate.
Deployed origin and authenticated tenant acceptance, remaining resolver validation,
stream/device parity, rollout/rollback and owner sign-off remain open.

## Worker ingress and Chat terminal-authority follow-up (2026-11-16)

At source `4b353fcc0aa352bf4920e1c67a903986fd503cdb`,
[full backend CI](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/43976337636/job/133681845172)
reported **17,168 passes, three failures, 44 skips and 14 passing subtests**.
The three failures still mocked the superseded raw update_run path. Their
fixtures now exercise the actual persist_run_outcome repository method through
the unit RPC transport, preserving terminal/proof and notification assertions.
These are contract repairs, not a reason to waive full backend CI.

Two worker defects are repaired: queued identities now load within their tenant
without imposing the interactive reader's default environment; execution then
uses the environment from the persisted row. Interactive callers retain their
environment filter. Step reads additionally require the same organization.
Terminal partial_success redelivery is held instead of dispatching another
execution. Queue schema and the existing worker injection seam remain stable.

The Chat finalizer no longer writes a raw intended terminal status when the
canonical finalizer raises. That fallback bypassed cancellation, proof and
transactional projection guards. Sentry/audit alerting remains, with an explicit
terminal_stamp_suppressed marker. The wrapper still does not propagate every
canonical persistence failure to every ingress response; complete ingress
honesty, in-flight revocation and provider readback remain unproven.

**21 additional real PostgreSQL cases are submitted to the existing QA12 lane**:
three persisted-environment worker reads; eight terminal/held redeliveries;
foreign-tenant denial; two actual Chat bridge success/failure duplicate callbacks
with real core SQL channels; late success after cancellation; five historical
preview classifications; and canonical-outage fallback preserving cancellation.
Controlled worker execution is explicitly not a provider acceptance test.
Current-revision CI is pending. No local executor is available for this batch;
earlier local checks on the restored unit fixtures do not certify these additions.

The read-only historical preview now distinguishes tenant conflicts, unsupported
lifecycles and missing version/lifecycle metadata before reporting matches_v2.
It was executed read-only on the attested acceptance project
`aadnwmjzrmbvadszroqt`: **15 linked failed/failed rows require metadata
reconciliation; 27 projection-only rows require domain classification**.
There are no missing linked step projections or observed step identity conflicts
in that inventory. Status equality alone is not parity. No backfill, reconciliation
journal, deletion or migration was installed. Historical changes require approved
row scope, compare-and-set guards, audit/undo evidence and consumer verification.

Deployment readiness is unchanged: the acceptance API is still on
`a91e4fd8a548631b7a252fc17f51c7a11d4841e4`, not this candidate. Its staged
`2702736d0ab798511dde594265010d598e44f17a` pin is stale and must not be accepted.
The new parameter/outcome/projection functions are not installed there.
Production's observed successful rollback reference is deployment
`78fb8af7-2c90-4a4f-9a34-180398ad20fb`, source
`557be844f191767ea51c9f1d1d4958e5b046ca53`; provider metadata says rollback
is available, which does not prove an executed rollback or restored behavior.
The removed QA build remains only a possible rollback candidate pending validation.

Voice PR610 remains draft at `02a4df66a76bb144f9a4c9584a075b07247152dc`.
The separate authored-dialogue work on PR611 is preserved. Device microphone,
speaker, interruption and reconnection acceptance still requires physical
observation. No provider mutation, release, rollback drill or owner sign-off was
performed. All 43 findings remain uncertified; original owners, dependencies,
consolidation dispositions and closure criteria are unchanged.


## Signed Chat ingress through persisted verification and consumer effect

The preceding source `179614f4d75cb0aff31aac0702724a87348eeb0d` passed all ten
consolidated CI lanes. [Full backend CI](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/43988147778/job/133721636628)
reported **17,193 passes, 44 skips and 14 passing subtests**; integration smoke
also passed. Its bounded [QA12 gate](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/43988147702/job/133721624686)
passed **130 actual PostgreSQL cases, 321 runtime guards and 43 routing/context
checks**. Those results certify that source's test gates, not this later candidate,
a full finding, deployment, physical device or third-party provider acceptance.

The signed HTTP Chat acceptance previously replaced claim/replay, canonical run
finalization and conversation outcome persistence with mocks. Two new durable
variants retain the actual Chat methods, real repository/RPC/projection functions,
core audit/inbox/learning writers and the declared asynchronous verifier body.
Conversation state uses a tenant-scoped SQL transport with row locks and the
production merge/outcome builders. The test receiver independently commits a
SQLite record and serves capability-scoped HTTP entity readback from that record.
Only the scheduler launch is captured; the actual scheduled verifier body runs.
The existing ledger-only variant remains, without weakening its replay checks.

This stronger ingress reproduced a caller defect: the provider context was
`synthetic` but the connector finalizer unconditionally persisted `production`.
The finalizer now takes environment identity from its execution context, with
explicit ingress identity for blocked paths and the prior production fallback
for legacy callers. All ten Chat finalization call sites carry ingress identity;
speculative deferral retains it. Eight focused cases cover positive/failed
outcomes, context precedence, blocked-path fallback and legacy behavior.

**Local validation: 54 focused Chat/verification cases, 38 orchestration/speculative
regressions, five joined signed-HTTP PostgreSQL/receiver journeys, two receiver
boundary cases and 17 register/release/consolidation guards pass.** The joined
suite first failed on the previous production environment literal, then passed
after the repair. This environment blocks Unix sockets, so a temporary local
runner used permitted loopback TCP for disposable PostgreSQL; repository/CI
harness and SQL were not modified. Exact-head hosted CI remains pending.
The fixture admits `verifying`, a production nonterminal state omitted from its
older minimal status constraint; every other previously admitted state remains
explicit, rather than dropping status validation.

The five joined cases are ledger replay, durable completion, cancellation before
verification completes, a revoked pending action and a different approving actor.
Durable completion requires actual HTTP-origin run/step rows, correct environment,
independent entity proof, matching contract projections, one core effect per store,
one terminal outbox event, actual relay delivery and one durable synthetic
consumer effect. Duplicate confirmation must create neither a second provider
write nor a second run/event. Before verification the run must be `verifying`,
the display projection `running`, and terminal outbox count zero. Cancellation
wins over a later verified callback; the already applied receiver effect remains
visible. Revoked/different-actor confirmations require zero provider writes,
ledger claims, runs, terminal events and success-channel records.

Boundaries remain explicit: policy/ownership lookup and vendor dispatch/read
transports are adapted; signed JWT and conversation-owner scoping execute, but
production membership, HITL database rows, conversation CAS/RLS and real vendor
OAuth are not certified. The consumer is synthetic, not evidence that every
production consumer is enabled. Cancellation here follows an applied receiver
write and precedes verification; it does not undo the provider write or prove
all live in-flight revocation races. Agent/Play paths still require their own
full ingress continuity. Historical reconciliation, physical voice/device and
deployed migration/rollback gates remain open. All 43 findings remain uncertified.


## Agent/Play terminal authority and cancellation projection integrity

At `93dbfe759fef6febc3ddd616f7bd6da520199c41`, eight CI lanes passed.
[Core CI](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/44010172157/job/133795086840)
stopped in the consolidated ingress gate with **87 passes and two failures**.
Both failures counted all conversation queries as exactly two; real outcome
channels perform additional conversation lookups in the full CI cohort. The
replacement assertion requires a successful exact conversation/org/actor ownership
check for **each HTTP request and before provider dispatch**. Queries returning
no owned row cannot satisfy that check. Contradictory ownership filters are also
rejected by the transport. All provider-count, durable state, projection, proof,
replay and outbox assertions remain. This changes the test from an incidental
query count to the actual authorization contract; it does not waive an ownership
check or make a source assertion substitute for execution.

The P27-02 AgentSelector -> Play -> approval -> actual step -> outbox journey no
longer replaces terminal finalization with a raw UPDATE. It now runs the canonical
terminal/proof/receipt transaction and actual core audit/inbox/learning writers.
Six cases cover approval, rejection, forbidden approver, foreign tenant,
cancellation committing between provider observation and finalization, and
terminal persistence failure. Approvals and the underlying run/step/contract rows
use the real repository. Policy/version/billing and vendor transport remain
adapted; the provider is an independent fixture process, not live HubSpot.

The cancellation case reproduced two application defects: the linear executor
returned `completed` although canonical SQL had committed `cancelled`, and a late
completed step left its display projection `running`. Both workflow runtimes now
consume one shared acknowledgement guard. It rejects absent/wrong-run/malformed
terminal acknowledgements and failed persistence, preserves canonical status and
refreshes a terminal conflict's projections through the existing locked-source
SQL function. No raw status fallback, second terminal event or duplicate fanout
is introduced. A failed terminal write raises rather than returning apparent
completion; its independently applied observation stays visible for recovery.
Generic nonterminal-writer atomicity and all other late-writer races are not
certified by this repair.

**Local validation:** 93 cases in the joined ingress/approval/Agent/Play cohort,
53 finalizer/caller contract cases, 269 workflow/ownership sweep cases, 16 native
recovery/receiver cases and 17 register/release/consolidation guards pass. Suite
counts overlap and are not presented as a unique combined test total.
The joined cohort includes all six Agent/Play cases and the corrected five Chat
cases. One pre-existing autonomous restart case was not included in that local
cohort: it explicitly restarts PostgreSQL over Unix sockets, blocked in this
workspace. The initial attempt reached 80 passes before that environment failure.
The repository/CI harness is unchanged; full hosted certification including that
case remains mandatory. Local supported PostgreSQL cases use the temporary TCP
runner described above. Two minimal caller fixtures now return an explicit typed
finalizer acknowledgement instead of None; their scope remains isolated, not
canonical persistence evidence. The graph unit fixture uses the same explicit
contract. Current-candidate CI remains pending, and no finding is closed.

[Operations CI](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/44010172158/job/133797121318)
also failed the real gVisor browser SIGKILL recovery contract on trial 1:
`fallback_reconciliation_required`, uncertain journal, durable checkpoint and
**zero fallback approved actions**. The broad recovery exception hid its cause.
This candidate adds an opt-in failure sink containing only a fixed stage and
allowlisted error class, plus those fields in the isolated certification failure
record. No exception text, task, URL, identity, model route or credential is
exported. A failing diagnostic sink must leave the fenced/uncertain decision
unchanged; both sink modes pass the revocation test. Recovery policy, the SIGKILL
assertion, authorization gates, resource limits and latency budgets are unchanged.
The underlying isolated recovery failure is **not yet diagnosed or repaired**;
it must pass with fresh exact-head evidence. No blind rerun is counted as a fix.

These are bounded gates under the original ECO-013/014, DEC-005/006/007/019 and
P27-02/03/04/06/08 owners. Live provider accounts, complete write/revocation
journeys, historical reconciliation, physical voice/device and deployed rollback
remain outstanding. No merge, hosted migration, provider mutation, deployment,
retirement or release authorization was performed; all 43 findings stay uncertified.

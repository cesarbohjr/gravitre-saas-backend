# PR605 Gate 26 — governed end-to-end runtime acceptance execution plan

**State: BLOCKED pending independent Security/Privacy and Operations/SRE approvals, exact-head integrated CI, and a deployed acceptance SHA.** This plan supplements the existing PR605 modernization, Gate 24/25/26, ECO remediation and DEC retirement records; it does not replace them. Approval ticket: [#607](https://github.com/cesarbohjr/gravitre-saas-backend/issues/607).

## Verified facts and evidence boundaries

- Source-owner inventory and privacy-safe edge-contract workflows **passed** at `67b61228`; full integrated CI was still pending, and the 26th real PostgreSQL consumer-effect test was in progress when checked. Do not carry success forward to a new commit SHA.
- The existing PostgreSQL suite previously passed **25 tests** in isolated CI; a 26th test now covers real terminal-trigger → outbox → relay → idempotent durable synthetic consumer effect and privacy-safe event/run link. Its new-head pass must be observed.
- The synthetic HMAC graph unit test emits agent/play/workflow/connector/outcome/consumer spans with fixture IDs. This is **not** evidence that those application components actually executed.
- Source-backed orchestration has three connector execution branches (human-approved, read-only parallel, policy-approved), but no single real acceptance trace has linked all agent/play/workflow/connector/outbox/consumer effects. Agent selection and play decision paths must be observed rather than assumed.
- Issue #607 is **open and not approved**: neither the Security/Privacy nor the Operations/SRE reviewer has posted an explicit dated approval. No production telemetry or remote acceptance execution is authorized yet.

## Preflight — hard stop before deployment or telemetry

1. Record the exact PR605 head SHA; all required CI and PostgreSQL acceptance checks must be **completed success** on that SHA. Treat pending/cancelled/skipped as not certified.
2. Obtain two independent dated APPROVE decisions on #607: Security/Privacy (purpose, retention/deletion, HMAC threat model, minimization, tenant isolation, notice/consent) and Operations/SRE (environment, sink, permissions, budget, key custody/rotation, stop time, rollback and named operator).
3. Confirm an isolated **non-production acceptance environment**, immutable deployed commit SHA, nonsecret service/project identifiers, test-tenant boundaries, disposable synthetic provider accounts, and owner of any external side effects. Never reuse production credentials or customer payloads.
4. Explicitly approve a narrow telemetry collection window; leave `PR605_EXECUTION_EDGE_TELEMETRY_ENABLED` off until then. Provision `PR605_EXECUTION_EDGE_HMAC_KEY` through the approved secret store; never paste its value in logs, CI, PR comments or reports. Document deletion of evidence and key after retention window.
5. Capture a baseline of actual feature flags and handler registrations: relay, outcome-learning, source-purge dry run, Temporal worker, connector availability, play/agent orchestration. A disabled feature is not a successful executed boundary.

## Acceptance scenarios — actual application and durable effects

| Scenario | Actual execution evidence required | Failure / safety criterion |
| --- | --- | --- |
| A. Read-only approved orchestration | HTTP/turn → agent selected → play invoked (if applicable) → workflow plan persisted → governed connector read invoked → outcome stored → outbox trigger → registered consumer executes and writes a durable effect | No simulated `emit_handoff` calls accepted as substitute for a real call; do not count a skipped/disabled play or consumer as covered |
| B. Human-approved write | Approval record and identity bound to run/action, execution after approval, provider read-back and durable outcome/consumer evidence | Denied/missing approval must produce zero provider writes and zero false terminal success |
| C. Revocation/cancellation | Revoke before dispatch, cancel mid-flight, replay cancelled turn | No unauthorized write or stale state; any provider-unknown result remains inconclusive |
| D. Retry and crash/restart | Outbox handler fails once, persists partial handler checkpoint, restarts and reclaims lease, produces exactly one idempotent effect | No duplicate side effects; no phantom delivery |
| E. Tenant isolation and privacy | Separate synthetic tenants, scoped access, HMAC span joins and approved log sink | No cross-tenant visibility; no raw org/user/run IDs, prompts, transcripts, tokens, provider responses or HMAC key |
| F. Kill switch and rollback | Disable telemetry and handler test flags, verify no subsequent spans and no residual processing | Stop by approved expiry; clean environment reset and evidence custody |

For each case preserve tested SHA, scenario ID, redacted pseudonymous root/plan/run/event relationships, actual persisted row/consumer-effect evidence, handler registration/feature flag state, observed authorization outcome, explicit PASS/FAIL/SKIP, and trace retention/deletion deadline. **Never infer a causal join from matching timestamps or independently generated IDs.**

## Remediation/retirement decisions

Classify each execution surface as **KEEP**, **UPGRADE**, or **CONSOLIDATE CANDIDATE** based on proven caller/consumer coverage. Do not approve removal of legacy ReAct, alternate voice paths, connectors, dual-run projections, outbox, Redis or Temporal until demonstrated replacement coverage, independent rollback and security signoff. Document each defect and linked regression test in PR605 ECO/DEC. Gate 27 release certification is separate.

## Current decision

**Do not deploy, enable production correlation, collect remote runtime traces, merge, backfill, or retire.** Finish exact-head CI, secure both #607 approvals and acceptance-environment identity, then execute the six scenarios under a named operator and capture redacted evidence.

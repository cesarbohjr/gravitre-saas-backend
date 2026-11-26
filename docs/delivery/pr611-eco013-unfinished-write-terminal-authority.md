# ECO-013 / DEC-005: terminal plans with unfinished writes

Base: `4dacbfc7196ff5323373b6e2fb870900fa9d66cc`. This is bounded source/test
engineering, not finding certification, provider acceptance, or a deployment.

## Exact-head prerequisite verification

All ten raw GitHub run records report success for that exact base SHA:

| Lane | Run | Attempt |
| --- | --- | --- |
| Core | [45173906022](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45173906022) | 1 |
| Operations | [45173906007](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45173906007) | 2 |
| QA04 | [45173906096](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45173906096) | 1 |
| QA12 | [45173906138](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45173906138) | 1 |
| Identity | [45173905986](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45173905986) | 1 |
| Data | [45173906211](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45173906211) | 1 |
| Intelligence | [45173906034](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45173906034) | 1 |
| Voice | [45173906256](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45173906256) | 1 |
| Browser | [45173906062](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45173906062) | 1 |
| Marketing | [45173906019](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45173906019) | 1 |

All five required Core jobs succeeded: Backend `137690208583`, Web
`137690208425`, Shared text/voice `137690208459`, Dependency audit
`137690208468`, Integration Smoke `137690208737`. Actual backend log:
**17,534 passed, 70 skipped, 14 passing subtests**; later offline checks passed.

QA12 actual-runtime job `137690232618` passed the checksum-pinned PostgREST
16.6 install, DEC-008 20 cases/zero skips, 16 shared gate unit checks, and
DEC-011 six cases/zero skips against PostgreSQL 18.7. Both actual ZIPs were
independently downloaded, hashed and parsed; they are not downloaded again:

| Gate | Artifact | ZIP SHA256 |
| --- | --- | --- |
| DEC-008 | `14818616778` | `34a091b239640fb66fd347d30224f463a3e37044b095be9495851a1159d095f4` |
| DEC-011 | `14818636871` | `b8545da7b8a218ddba13e10c7305b09a5cd4818f5abe1f77772c107bd1e692c9` |

Each sole evidence JSON has exact base `git_sha`, `status=PASS`, its required
count, `skipped=0`, `external_project_used=false`, `certifies_whole_finding=false`
and `provider_acceptance=NOT_RUN`. DEC-011 expected PostgreSQL version is 18.7.

Operations initially failed before worker execution: job `137691498497`,
`owned_https_fixture_readiness`, two `origin_unreachable` quick-tunnel attempts.
Authenticated actor/cross-tenant RLS passed first. Native-worker source diff
from parent b1ec821 to base 4dacbfc is empty. Artifact `14820140544` was independently
downloaded/parsed, ZIP SHA256
`40592dc4a2381d87fc2006dbae26c8c26fd665a5c00d5ba7dfd169cc4a0c25ea`.
One diagnosed single-job retry `137727669005` passed: 25 scenario records,
including 24 adapter/worker cases, all passed; fixture attempt ready. Initial
infrastructure failure remains evidence, not erased by retry success. No readiness
guard was loosened. Skipped live/provider/billing/signed jobs and physical-voice
reserved offline schema/simulation checks are not live acceptance.

## Actual source path and newly reproduced gap

The existing `enrich_task_state_patch` ingress can bridge a legacy pending WRITE
to `ExecutionPlan(source=pending_task_bridge)`. `AgentIntelligence` concretely
reconciles/persists plans and builds/finalizes `ReactPlanRuntime`; ReAct dispatch
uses `decide_execution_loop`. Its cancelled durable-session decision sets the
plan terminal without rewriting pending/running steps. `finalize_react_execution_plan`
also produces failed, blocked, partial and verification-inconclusive plans while
unfinished write steps remain. This is source tracing, not deployed usage proof.

The actual writer is `ConversationStateService.update_task_state` -> synchronous
read/merge under its conversation lock -> `enrich_task_state_patch` ->
`prefer_persisted_write_plan`. Its existing task-revision compare-and-set reloads
on conflict. The same authority helper is used by plan continuation. Prior tests
protected connector-source terminals and completed write steps; those did not
cover the unfinished-step shapes above.

On unmodified base source, the first 29-case reproduction reported **28 failed,
one control passed**: 20 older/equal-revision approval patches replaced terminal
plans; five continuations reopened them; two actual state-writer cases lost
cancellation (including a simulated revision conflict); a grouped control also
failed its existing weak/nonterminal-replan preservation assertion. The
in-flight-write/read-only control passed. Synthetic storage enforced the emitted
org/conversation and task-revision predicates. No database/provider was contacted.

## Bounded repair and verification

`is_terminal_write_plan` now recognizes an existing protected terminal status
when any write step exists, regardless of that step's pending/running status.
The two existing connector-source exceptions are retained. Terminal statuses,
revision comparison, distinct-plan approval handling, newer terminal evidence,
weak-source behavior and existing nonterminal replan policy are unchanged.
No dispatch executor, new approval authority, schema or migration is added.

The final new file contains **31 passing cases** (two weak-compose cases added
after the initial reproduction). It exercises actual bridge, loop/finalizer,
continuation, authority and conversation writer. After stored cancellation, a
reconstructed actual ReAct runtime refuses dispatch with
`react_dispatch_blocked:cancelled` even without a durable-session side channel.
The CAS-conflict case verifies reload, retained other-writer state, revision 10
and cancelled pending projection. Distinct actions/newer terminal evidence and
in-flight/read-only controls remain supported. Storage remains an in-memory
double: this is not SQL/CAS concurrency or RLS proof and no provider was invoked.

Normal backend conftest loaded. The broader targeted invocation reported
**210 passed, zero skips**, plus **four existing route scenarios unable to start**
because `ScenarioHarness` imports `app.main` -> SSO router and this task Python
lacks `onelogin`. Those four are not assertion regressions or passes; hosted
Core must execute them with normal dependencies. Covered passing suites include
authority, lifecycle, E5 convergence, conversation I/O/revision conflict,
observation cancellation, autonomous loop, continuity/checkpoints, text/voice
task parity and P0-P6 convergence. An earlier overlapping focused invocation
passed 159 before the two additional compose cases; do not sum totals.

No full AgentIntelligence/model/provider journey or live race timing is certified.
Independent durable consumer observation, all producer/surface authority,
revocation, deployed behavior, owner approval and rollback remain open. The
register records bounded progress only for ECO-013/DEC-005, plus completed
prior DEC-011 hosted evidence; all closure/release booleans remain unchanged.
Twelve installed workflows and independent mandatory PostgREST counts 20 and six
remain unchanged. Next gate: full hosted CI on the resulting exact head and both
mandatory artifacts. No merge/deploy/live dispatch/provider writes or closure.
The completed signed QA preflight and independent cleanup are preserved, unrepeated.

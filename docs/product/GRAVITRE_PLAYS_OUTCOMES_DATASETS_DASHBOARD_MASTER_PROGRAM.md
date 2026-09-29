# GRAVITRE — PLAYS, OUTCOMES, DATASETS & DASHBOARD MASTER PROGRAM

Durable specification record. Authoritative source: Cesar's directives.
Sections below are stored **verbatim** (inside fenced blocks). Do not paraphrase, shorten or
replace them with a roadmap.

Order of authority:

1. Phase -1 — Product Convergence + Capability Contract (addendum; precedes Phase 0)
2. Phase -1 acceptance and program sequencing (2026-09-28)
3. Owner-live gate + Master Program preservation (2026-09-28)
4. Phases 0 through 17 — the Master Program body

## Record status

| Section | Status |
|---|---|
| Phase -1 addendum | VERBATIM — recorded 2026-09-28 |
| Phase -1 acceptance / sequencing | VERBATIM — recorded 2026-09-28 |
| Owner-live gate directive | VERBATIM — recorded 2026-09-28 |
| Phases 0–17 body | **SOURCE GAP — NOT RECORDED VERBATIM**. The available repository/source material contains the Phase -1 addendum and sequencing references but not the complete original Phase 0–17 body. It is intentionally not reconstructed or paraphrased as if verbatim. Implementation evidence is tracked in the phase audit/decision/status documents. |

Phase -1 results: `docs/platform-reconciliation/phase-minus-1-findings.md` (and the full product contract in
local tag `local/capability-registry-phase-minus-1`).

---

## 1. Phase -1 addendum — Product Convergence + Capability Contract (verbatim)

````text
# GRAVITRE — PLAYS, OUTCOMES, DATASETS & DASHBOARD MASTER PROGRAM
# PHASE -1 ADDENDUM — PRODUCT CONVERGENCE + CAPABILITY CONTRACT
Before executing Phase 0 of the master program, establish the actual unified
Gravitre product baseline.
This step is mandatory.
The core product has been consolidated onto main.
The Gravitre 3.0 Plus frontend currently exists on its dedicated feature branch.
Do NOT begin building Plays against assumptions about either side.
First determine exactly what the existing backend/runtime provides and exactly
what the new frontend currently consumes.
The objective is to create ONE PRODUCT CONTRACT between:
CORE RUNTIME
and
GRAVITRE 3.0 PLUS FRONTEND.
No parallel runtime.
No frontend-only fake product state.
No duplicate backend abstraction.
==================================================
PHASE -1A — CORE CAPABILITY INVENTORY
==================================================
Inspect the current main branch.
Produce an authoritative registry of what Gravitre can actually do today.
Inventory at minimum:
AGENTS
- agent types;
- agent identities;
- departments;
- models/providers;
- tools;
- permissions;
- autonomy/trust level;
- context;
- knowledge;
- memory;
- work history;
- outcomes where available;
- delegation/council relationships.
TOOLS / ACTIONS
- canonical ActionSpecs;
- tool IDs;
- provider;
- READ / WRITE classification;
- risk;
- approval requirement;
- input schema;
- output schema;
- executable state;
- connector dependency.
CONNECTORS
- provider IDs;
- connection state;
- authentication state;
- capabilities;
- available actions;
- READ capabilities;
- WRITE capabilities;
- approval requirements;
- health/live state;
- source access;
- sync capability.
WORKFLOWS
- schema;
- node types;
- triggers;
- schedules;
- conditions;
- branching;
- agents;
- connectors/actions;
- approvals;
- outputs;
- execution state;
- run history;
- retries;
- cancellation;
- artifacts;
- Observations;
- events.
AI / COGNITIVE RUNTIME
- conversation;
- CognitiveTurnKernel;
- Intent Gateway;
- ExecutionPlan;
- ActionSpec;
- PendingAction;
- Observation;
- Response Composer;
- follow-up continuity;
- memory;
- artifacts;
- Computer Use;
- voice.
GOVERNANCE
- RBAC;
- tenant isolation;
- trust/autonomy;
- approval policy;
- risk;
- WRITE restrictions;
- audit records;
- HMAC integrity;
- duplicate protection.
KNOWLEDGE / INTELLIGENCE
- sources;
- knowledge graph;
- relationships;
- evidence;
- provenance;
- GIBE;
- learning events;
- recommendations;
- organizational context.
BUSINESS / OUTCOME DATA
- existing outcome tables/models;
- KPI models;
- execution outcomes;
- result state;
- verification;
- attribution;
- business events;
- activity records.
DASHBOARD
- every endpoint/data hook;
- metrics;
- filters;
- date-range behavior;
- outcome data;
- execution data;
- agent data;
- connector data;
- workflow data;
- saved configuration.
EVENTS
- execution events;
- workflow events;
- agent events;
- Observation events;
- approval events;
- connector events;
- business/result events.
For each capability record:
CAPABILITY
CANONICAL ID
BACKEND MODULE
API / EVENT
SCHEMA
TENANT-SCOPED?
READ / WRITE
APPROVAL?
FRONTEND CONSUMER
STATUS
NOTES
==================================================
PHASE -1B — FRONTEND CAPABILITY INVENTORY
==================================================
Inspect:
feat/gravitre-3.0-plus-frontend
Map every major product surface to its actual backend/runtime dependency.
At minimum:
Dashboard
AI Workspace
Assignments
Agents
Agent Detail
Approvals
Workflows
Workflow Builder
Schedules
Goals
Activity
Connectors
Sources
Marketplace
Intelligence
Model Studio
Governance
For every surface record:
SURFACE
DATA REQUIRED
CURRENT API
CURRENT HOOK
CURRENT MOCK/FIXTURE
REAL BACKEND AVAILABLE?
WIRING GAP?
PROTECTED CORE SEAM?
REGRESSION RISK?
Identify every place where the redesigned frontend currently relies on:
- fixture-only data;
- inferred data;
- old endpoint;
- deprecated API;
- placeholder state;
- local composition that should come from canonical runtime state.
Do NOT silently replace fixture data with guessed live state.
==================================================
PHASE -1C — FRONTEND ↔ CORE CONTRACT MATRIX
==================================================
Produce one matrix:
PRODUCT CONCEPT
→ CANONICAL BACKEND SOURCE
→ API / EVENT
→ FRONTEND SURFACE
→ STATUS.
Examples:
Agent identity
→ canonical agent record
→ agents API
→ Agent Detail / Builder / Assignments
→ WIRED / PARTIAL / MISSING
Tool capability
→ ActionSpec
→ catalog API
→ Connectors / Agent capabilities / Builder
→ ...
Approval
→ PendingAction / policy
→ approval API
→ Approvals / AI / Builder
→ ...
Execution
→ ExecutionPlan + Observation
→ conversation/workflow state
→ AI / Assignments / Dashboard
→ ...
Artifact
→ work_artifact
→ artifact API
→ AI / Assignments / Dashboard
→ ...
Outcome
→ existing outcome/result model if present
→ outcome API
→ Dashboard / Plays
→ ...
This becomes the product integration contract.
==================================================
PHASE -1D — CLOSE PRODUCT WIRING GAPS FIRST
==================================================
Before adding Plays, fix only integration gaps that prevent the existing core
from being accurately represented in Gravitre 3.0 Plus.
Examples may include:
- canonical agent permissions not shown correctly;
- ActionSpecs not reflected in connector capability UI;
- approvals not bound to PendingAction;
- workflow execution state not bound to Observations;
- artifacts not represented consistently;
- dashboard using stale or duplicate state;
- Intelligence using fixture state where canonical state exists.
Do NOT add new capability while fixing these seams.
This is convergence, not feature expansion.
==================================================
PHASE -1E — CREATE THE GRAVITRE CAPABILITY REGISTRY
==================================================
Create one reusable internal capability registry derived from canonical systems.
It should make it possible for the Play layer to ask:
Which agents exist?
Which connectors are available?
Which tools/actions exist?
Which tools can READ?
Which tools can WRITE?
Which actions require approval?
Which workflow primitives are supported?
Which signals/events exist?
Which business metrics exist?
Which data hooks exist?
Which evidence can be produced?
Which verification mechanisms exist?
Do NOT hard-code a separate Play capability catalog if the canonical catalogs
already contain this information.
Compose from existing systems wherever possible.
==================================================
PHASE -1F — PLAY READINESS MATRIX
==================================================
Before building the first Play, produce:
PLAY
REQUIRED SIGNALS
REQUIRED CONNECTORS
OPTIONAL CONNECTORS
REQUIRED AGENTS
REQUIRED ACTIONS
REQUIRED APPROVALS
VERIFICATION SOURCE
OUTCOME METRICS
CURRENT READINESS
for:
Customer Rescue
Revenue Recovery
Marketing Performance.
Classify each dependency:
AVAILABLE
PARTIAL
MISSING
EXTERNAL_CONNECTION_REQUIRED.
This determines what each Play can truthfully do today.
==================================================
PHASE -1G — DO NOT REQUIRE EVERY PLAY TO BEGIN WITH WRITE
==================================================
Design Plays to provide value progressively.
A Play may operate at four truthful maturity levels:
OBSERVE
Detect and assemble the opportunity/problem.
RECOMMEND
Produce an evidence-backed recommended response.
ACT WITH APPROVAL
Prepare actions and execute only after governance approval.
ACT WITHIN POLICY
Execute automatically only where the existing policy system explicitly permits.
The same Play should progress through these states based on available
connectors, permissions and policy.
Do NOT build separate Play implementations for each level.
==================================================
PHASE -1H — DAY-ONE VALUE REQUIREMENT
==================================================
Every initial Play must produce useful output before full automation is
configured.
A user connecting relevant systems should quickly receive something like:
CUSTOMER RESCUE
"12 accounts show credible churn risk. 4 need attention now. Here is the
evidence and recommended intervention."
REVENUE RECOVERY
"8 stalled or recoverable revenue opportunities were found across your
connected systems. Here is why each qualifies."
MARKETING PERFORMANCE
"Three campaigns show material downstream inefficiency. Here is the path from
spend to lead quality to pipeline."
These are examples of EXPERIENCE, not permission to fabricate values.
All displayed values must come from the user's actual connected data.
A Play must remain useful in Observe/Recommend mode even if WRITE permissions
have not yet been granted.
==================================================
PHASE -1I — NO PLAY WITHOUT EVIDENCE
==================================================
Every Play result must distinguish:
SIGNAL
what was detected.
CONTEXT
what relevant information was assembled.
RECOMMENDATION
what Gravitre thinks should happen.
ACTION
what Gravitre actually executed.
VERIFICATION
what changed afterward.
OUTCOME
what business result can be supported.
Do not collapse these states into one "success" label.
==================================================
PHASE -1J — DEFER NON-CRITICAL DATASET PROVIDER WORK
==================================================
The Dataset / Model Studio audit remains part of the master program.
However:
Hugging Face and other external dataset-provider implementation must NOT block
the first three Play implementations unless one of those Plays genuinely
requires that capability.
Priority order is:
1. product convergence;
2. capability registry;
3. Play abstraction;
4. outcome/evidence contract;
5. first three Plays;
6. dashboard outcome presentation;
7. live Play proof;
8. dataset-provider expansion.
Dataset architecture may be designed earlier.
Provider implementation may occur later.
==================================================
PHASE -1K — REQUIRED OUTPUT BEFORE PHASE 0 CONTINUES
==================================================
Return:
1. Core capability inventory.
2. Frontend capability inventory.
3. Frontend ↔ core contract matrix.
4. Wiring gaps.
5. Capability registry architecture.
6. Play readiness matrix.
7. Existing outcome architecture.
8. Existing evidence architecture.
9. Existing dashboard data hooks.
10. Any true architecture decisions still OPEN.
Then continue directly into the existing Master Program.
Do not create another roadmap.
Do not stop merely because some authenticated acceptance step is unavailable.
````

---

## 2. Phase -1 acceptance and program sequencing (verbatim)

````text
# CESAR — GRAVITRE PLAYS / OUTCOMES PROGRAM
# PHASE -1 ACCEPTED — CONTINUE WITH THE FULL MASTER PROGRAM
The Phase -1 convergence work is accepted.
Do NOT invent Plays yet on the current frontend branch.
The findings are useful and change the implementation sequence.
AUTHORITATIVE PROGRAM
The Master Program is the full specification previously supplied by Cesar:
GRAVITRE — PLAYS, OUTCOMES, DATASETS & DASHBOARD MASTER PROGRAM
Phases 0 through 17 remain authoritative.
The Phase -1 Product Convergence + Capability Contract directive precedes that
program.
Do not replace the Master Program with only the abbreviated -1J priority order.
==================================================
1. RECORD THE PHASE -1 FINDINGS
==================================================
Preserve the current product-contract findings:
- Plays do not currently exist as a canonical product abstraction.
- goal progress has no canonical backend source.
- stored business metric values do not currently exist.
- metric definitions exist, but definitions are not measured values.
- agents / assignments / evidence are partially wired.
- some frontend routes still derive or fill state themselves.
- capability registry currently covers:
  - 85 vendors
  - 731 actions
  - 362 WRITE actions
- 283 WRITE actions currently have provider-acceptance evidence only and no
  independent post-action verification.
- no initial Play is currently LIVE_READY.
- external organization connection readiness has not yet been evaluated.
Do not overstate any of these.
==================================================
2. DO NOT PUSH THE LOCAL MAIN COMMIT DIRECTLY YET
==================================================
573c249a contains the capability registry / contract work.
Do not push directly to main merely because the registry is useful.
Main is a production-deploy branch.
The capability registry requires an explicit core/frontend API seam first.
The core agent will own that seam.
Preserve the local work and coordinate rather than duplicating it.
==================================================
3. CAPABILITY REGISTRY CONTRACT
==================================================
The frontend must consume the registry through a canonical authenticated,
tenant-scoped, read-only API.
Do not:
- import backend Python internals into frontend assumptions;
- duplicate the registry in TypeScript;
- create another action catalog;
- create a Play-specific connector/action catalog.
Expected conceptual interface:
GET /api/capabilities
or the repo's canonical API equivalent.
It should expose only canonical data the current user/org is allowed to see.
The frontend may build views over it but may not redefine capability truth.
==================================================
4. AUTONOMY IS BLOCKING UNTIL RECONCILED
==================================================
Do not implement Play autonomy based on the current frontend interpretation.
Current finding:
"no approval policies set" appears to allow WRITE actions to run automatically.
That must be reconciled against the canonical governed-WRITE runtime.
The frontend must not independently decide that:
no policy == autonomous.
Until core proves the canonical rule, display the actual runtime-derived policy
state only.
Do not expose "Act within policy" as available unless the runtime can prove that
the corresponding action would be permitted to auto-run.
==================================================
5. OUTCOME ARCHITECTURE — DO NOT BUILD A GENERIC KPI STORE FIRST
==================================================
The next genuinely new product primitive is likely the canonical business
Outcome contract.
Do NOT immediately create a generic metric-values table.
Follow the Master Program Phase 3 and Phase 4 audit first.
Preferred model:
WORKFLOW / ACTION
→ OBSERVABLE RESULT
→ VERIFICATION
→ OUTCOME EVENT
→ AGGREGATION
→ DASHBOARD
OutcomeEvent should be the business-result ledger if no existing schema already
serves that function.
Dashboard KPIs should aggregate from:
- verified OutcomeEvents;
- canonical workflow/execution data;
- real external system-of-record values.
Only introduce a separate metric-value store if a real use case cannot be
represented by those canonical sources.
==================================================
6. PROVIDER ACCEPTANCE IS NOT BUSINESS VERIFICATION
==================================================
The audit found 283 WRITE actions whose evidence is only that the vendor
accepted the request.
For the Plays program:
HTTP/provider acceptance
!=
verified business outcome.
Such actions may support:
ACTIONED
but must not automatically produce:
VERIFIED SUCCESS.
Verification may require:
- re-read of the mutated record;
- downstream system state;
- webhook/event;
- independently observed source record;
- explicit human verification;
- another existing canonical verification mechanism.
Preserve this distinction in the Outcome contract.
==================================================
7. FINISH FRONTEND CONVERGENCE BEFORE PLAYS
==================================================
The current 3.0 Plus frontend branch must first converge with latest main.
Required:
1. fetch latest main;
2. inspect divergence;
3. merge/rebase according to repository policy;
4. preserve newer main chat-result/artifact work;
5. resolve frontend/core seams without regressing either;
6. rerun:
   - lint
   - typecheck
   - Vitest
   - build
   - required CI
7. prepare owner-live Preview.
Do not start Play feature implementation on a stale frontend base.
==================================================
8. OWNER-LIVE BEFORE THE PLAY BRANCH
==================================================
Finish the 3.0 Plus acceptance path first.
OWNER_LIVE_ACCEPTANCE must cover the real product surfaces and canonical state.
If owner-live exposes core/frontend contract defects, fix those before Plays.
After acceptance:
merge Gravitre 3.0 Plus into main using the approved process.
Then create a NEW feature branch from unified main for Plays / Outcomes.
Suggested branch:
feat/gravitre-plays-outcomes
Do not turn feat/gravitre-3.0-plus-frontend into the permanent Plays branch.
==================================================
9. PLAY IMPLEMENTATION CRITICAL PATH
==================================================
Once unified main exists, execute the Master Program in this practical order:
A. Phase 0 repository/architecture audit
B. Phase 2 Play architecture audit
C. Phase 3 Outcome system audit
D. Phase 4 canonical Outcome contract if required
E. Phase 5 evidence / verification wiring
F. capability-registry consumption
G. Customer Rescue
H. Revenue Recovery
I. Marketing Performance
J. dashboard template infrastructure
K. Play dashboard templates
L. live Play verification
M. dataset / Model Studio provider expansion
Phase 1 dataset architecture audit may happen early.
Hugging Face implementation must NOT block the first live Play.
==================================================
10. PLAY MATURITY MODEL
==================================================
All three Plays should use one progressive maturity model:
OBSERVE
RECOMMEND
ACT WITH APPROVAL
ACT WITHIN POLICY
VERIFY
OUTCOME
This is NOT six separate Play implementations.
Available maturity depends on:
- connected systems;
- ActionSpecs;
- data availability;
- agent permissions;
- canonical approval policy;
- verification capability.
A Play should still provide useful value in OBSERVE / RECOMMEND mode.
==================================================
11. FIRST-RESULT EXPERIENCE
==================================================
Optimize the initial Plays around immediate credible insight.
A newly configured user should not need full WRITE access to see value.
Customer Rescue should be able to identify supported risk evidence.
Revenue Recovery should be able to identify supported stalled/recoverable
opportunities.
Marketing Performance should be able to identify supported inefficiency or
handoff issues.
Do not promise that these signals exist when required data is absent.
Use honest readiness / insufficient-data states.
==================================================
12. DO NOT IMPLEMENT FROM THIS PROMPT YET
==================================================
For now:
- complete frontend/main convergence;
- consume the core capability seam once provided;
- prepare owner-live;
- preserve the Master Program and Phase -1 findings.
Do NOT build Play tables or Outcome tables on the frontend branch.
The Play program begins from unified main after frontend acceptance.
````

---

## 3. Owner-live gate + Master Program preservation (verbatim)

````text
# CESAR — PHASE -1 COMPLETE
# OWNER-LIVE GATE + MASTER PROGRAM PRESERVATION

The convergence work is accepted.

Current frontend branch:

feat/gravitre-3.0-plus-frontend

Current merged head:

efc0c988

Latest main included:

2807a089

The branch now contains the newer chat-result and artifact work from main.

CI run:

36505964385

Current status:

- Web lint/typecheck/build = PASS
- Backend pytest = PASS
- Shared runtime text/voice gate = PASS
- Dependency audit = PASS
- Integration Smoke = PASS
- Billing E2E = still running / not yet classified

Do not count Billing E2E as PASS until it completes.

==================================================
1. STOP SEARCHING FOR THE MASTER PROGRAM
==================================================

The full Master Program already exists in Cesar's directive.

It is:

GRAVITRE — PLAYS, OUTCOMES, DATASETS & DASHBOARD MASTER PROGRAM

with Phases 0 through 17.

Treat that supplied directive as authoritative.

Add it to the repository now as a durable specification document.

Suggested location:

docs/product/GRAVITRE_PLAYS_OUTCOMES_DATASETS_DASHBOARD_MASTER_PROGRAM.md

Place the Phase -1 Product Convergence + Capability Contract addendum before
Phase 0.

Do not paraphrase it into a shorter roadmap.

Preserve the full requirements and sequencing.

This prevents future context loss.

==================================================
2. DO NOT START PLAYS ON THIS BRANCH
==================================================

feat/gravitre-3.0-plus-frontend remains the frontend convergence/release branch.

Do not add:

- Play schema
- OutcomeEvent tables
- dashboard Play templates
- dataset provider integrations
- Hugging Face
- Play execution logic

to this branch.

The Plays program begins only after 3.0 Plus is owner-live accepted and merged
into unified main.

==================================================
3. OWNER-LIVE IS NOW THE GATE
==================================================

Preview:

https://gravitre-saas-backend-ed8ww4qhc-gravitre-ai.vercel.app

OWNER_LIVE_ACCEPTANCE = NOT_RUN

Prepare the branch for Cesar's real signed-in owner walk.

No fixture/e2e route counts as owner-live proof.

The owner walk should cover:

Dashboard
AI Workspace
Assignments
Agents
Agent Detail
Approvals
Workflows
Workflow Builder
Connectors
Sources
Intelligence
Marketplace
Model Studio
Governance

==================================================
4. OWNER-LIVE CONTRACT CHECK
==================================================

During the owner walk, verify that every major surface is using canonical state.

For each route check:

- real organization data appears;
- navigation works;
- no fixture state leaks;
- no stale/deprecated endpoint is used;
- approvals reflect governed runtime state;
- agent permissions reflect canonical backend state;
- artifacts render from canonical artifact data;
- workflow state reflects backend execution state;
- connector capability state reflects actual connections/action catalog;
- Intelligence does not invent state;
- Ask Gravitre preserves current context;
- AI streams correctly.

If any surface fails:

classify it as:

FRONTEND WIRING DEFECT
CORE/API DEFECT
AUTH/SESSION DEFECT
DATA AVAILABILITY
EXTERNAL CONNECTION STATE

Do not patch around canonical state with local mock logic.

==================================================
5. AUTONOMY TEXT REMAINS CONSERVATIVE
==================================================

Keep the current frontend wording:

- display recorded policy only;
- do not promise unattended WRITE execution;
- per-action approval is determined by canonical governed runtime.

Do not restore language such as:

"writes run automatically unless approval settings require confirmation"

until the core agent proves the runtime rule and exposes a canonical effective
policy.

==================================================
6. CAPABILITY REGISTRY REMAINS CORE-OWNED
==================================================

The local commit:

573c249a

remains preserved and tagged:

local/capability-registry-phase-minus-1

Do not push it directly from the frontend workflow.

The core agent owns review and delivery of the authenticated tenant-scoped
read-only capability seam.

Frontend should consume that seam once it is available.

Do not duplicate the registry in TypeScript.

==================================================
7. PUBLIC DOC ISSUES
==================================================

Record these separately from Plays:

- SDK install lines have not been verified against actual published packages;
- five public docs pages reference removed /api/operator/* endpoints.

Do not silently rewrite them unless verified.

Classify each as:

VERIFIED_CORRECT
STALE
UNVERIFIED

and fix only what can be proven.

==================================================
8. BILLING E2E
==================================================

When run 36505964385 finishes:

if PASS:
record PASS.

if cancelled/time-limit:
record INCONCLUSIVE_TIMEOUT.

if FAIL:
classify whether each failure is:
- test/harness defect
- auth/setup defect
- real product defect.

Do not hide a real signed-in product failure because it predates this branch.

==================================================
9. MERGE READINESS
==================================================

Do not merge yet.

MERGE_READY remains NO until:

- owner-live walk is complete;
- any real convergence defects are fixed;
- exact final SHA CI is green for required jobs;
- Billing E2E is properly classified;
- no known critical signed-in product defect remains.

==================================================
10. AFTER OWNER-LIVE ACCEPTANCE
==================================================

Once owner-live is accepted:

1. commit any final convergence fixes;
2. run exact-SHA CI;
3. merge feat/gravitre-3.0-plus-frontend into main;
4. deploy through the approved production process;
5. run production smoke;
6. confirm integrated product health.

Then create:

feat/gravitre-plays-outcomes

from the new unified main.

That branch will execute the full:

GRAVITRE — PLAYS, OUTCOMES, DATASETS & DASHBOARD MASTER PROGRAM

starting with Phase 0.

Do not start that program earlier.
````

---

## 4. Phases 0–17 — Master Program body

**SOURCE GAP — NOT RECORDED VERBATIM.** The currently available source record does not contain
the complete original Phase 0–17 body. Do not fabricate or backfill a paraphrase under a
"verbatim" label. The implemented phase evidence is recorded in
`GRAVITRE_PLAYS_PHASE_0_ARCHITECTURE_AUDIT.md`,
`GRAVITRE_PLAYS_DATASET_MODEL_STUDIO_AUDIT.md`,
`GRAVITRE_PLAYS_OUTCOME_PERSISTENCE_DECISION.md`,
`GRAVITRE_PLAYS_WORKFLOW_BINDING_DECISION.md`,
`GRAVITRE_PLAYS_DASHBOARD_INTEGRATION_DECISION.md`,
`GRAVITRE_PLAYS_PHASES_14_17_CLOSEOUT.md`, and
`GRAVITRE_PLAYS_SEQUENCE_STATUS.md`.

<!-- PHASES 0-17 VERBATIM BELOW -->

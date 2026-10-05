# Gravitre design intent sweep — 2026-10-04

Original reviewed head: `d5ae83d1`, draft PR #298. The original review below preceded implementation; the implementation continuation and validation are recorded at the end.

## Verdict and evidence boundary

The implementation has substantial functional depth and distinct compositions. It is not yet a fully converged expression of Gravitre as an AI operating layer. Several deeper routes retain misleading data, local execution claims, decorative motion and older type/material rules. Those are more consequential than moving cards around.

Fresh static discovery covers **176 route modules: 109 product/legacy-product, 31 public/auth/support and 36 fixture/development**. Import traversal plus Next ancestor boundaries reaches **364 control/disclosure source files**. Every route was scanned for composition, headings, local dependencies and controls; representative and high-risk journeys were manually inspected. That is not a manual click-through of every conditional button or permission state. The accompanying CSV records the depth and intended job of every route. An absent composition attribute or selection hook is a review signal, not by itself a defect.

The current development server started on port 3055. Browser navigation to `/e2e/shots/home` failed with `net::ERR_BLOCKED_BY_CLIENT`. No current app screenshot was obtained. The [Product Design audit skill](sandbox:/root/.codex/plugins/cache/openai-curated-remote/product-design/0.1.56/skills/audit/SKILL.md) requires: “If none of those can capture valid screenshots or control the flow, stop and report the blocker.” That limits the visual audit; the requested source/design-plan review continues. Consequently this is a **source/design-contract review**, not completed visual acceptance. Historical fixture screenshots, Cursor's reported tests and old previews do not establish geometry for this SHA. No tests were rerun because no product implementation changed.

`VISUAL_ACCEPTANCE = BLOCKED / NOT_RUN`; `OWNER_LIVE_ACCEPTANCE = NOT_RUN`; `IMPLEMENTATION_COMPLETE = NO`; `MERGE_READY = NO`. No merge or deployment performed.

## Authority cross-reference

The recovered `GRAVITRE_3_0_PLUS_MASTER_SPEC.md` remains authoritative for product behavior: Ask → Understand → Plan → Visualize → Modify → Approve → Execute → Observe → Learn. AI reduces navigation while preserving expert workspaces; it is not simply another chat button.

Fresh Figma contexts and screenshots inspected from file `OsDKeRy9HwfSKR3e9YyOFM`:

| Reference | What it establishes |
|---|---|
| [Foundation 17:2](https://www.figma.com/design/OsDKeRy9HwfSKR3e9YyOFM?node-id=17-2) | Emerald/carbon/bone palette, Space Grotesk display and Inter body, semantic hierarchy; one system, different compositions |
| [Responsive 20:2](https://www.figma.com/design/OsDKeRy9HwfSKR3e9YyOFM?node-id=20-2) | Recompose information architecture before removing information; phone task focus and disclosure; tablet keeps analytical content |
| [Handoff 22:2](https://www.figma.com/design/OsDKeRy9HwfSKR3e9YyOFM?node-id=22-2) | Five page families, preserved capabilities, 44px targets, explicit route/state acceptance |
| [Intelligence 10:5](https://www.figma.com/design/OsDKeRy9HwfSKR3e9YyOFM?node-id=10-5) | Evidence relationship map and why it matters, rather than another inventory dashboard |
| [Agents 10:52](https://www.figma.com/design/OsDKeRy9HwfSKR3e9YyOFM?node-id=10-52) | Specialist identity, responsibility and capability relationships |
| [Activity 10:101](https://www.figma.com/design/OsDKeRy9HwfSKR3e9YyOFM?node-id=10-101) | Quiet operating queue with decisions embedded in work |
| [Builder 10:159](https://www.figma.com/design/OsDKeRy9HwfSKR3e9YyOFM?node-id=10-159) | Workspace leads; configuration follows selected work |
| [Expression/motion 24:2](https://www.figma.com/design/OsDKeRy9HwfSKR3e9YyOFM?node-id=24-2) | Connections are the artwork; paths represent real behavior; no ambient floating or perpetual decorative motion |

Also cross-referenced the AI-native architecture, interaction system, token provenance, creative product UI grammar, previous design-led review and current surface queue. Older Nodus/Carbon documents explain existing implementation but cannot silently supersede page-03 identity. Figma reference metrics and names are specimens, not product data. Page-03 properties are layer measurements, not an exported variable collection.

## Findings with corrections and acceptance

Priority: P0 = misleading execution/evidence; P1 = material journey/design-contract gap; P2 = convergence and usability. Source locations below are relative to the repository and searchable by the named function/element.

| ID | Priority | Current evidence | UX consequence and intentional correction | Acceptance |
|---|---|---|---|---|
| D01 | P0 | `apps/web/app/workflows/[id]/builder/page.tsx`, `DebateViewDialog` acceptance callback: local `handleUpdateNode`, default confidence `100`, `executedAction` copied from recommendation, toast “recommendation has been executed” | A local graph edit claims an external action and manufactures certainty. Keep recommendation acceptance distinct from actual execution. Use a real execution/approval contract if available; otherwise save configuration with honest copy and no executed marker. | Accept without a runtime result cannot show executed, verified or 100% confidence. Failed persistence preserves review. Actual runtime evidence links to its run/action ID. |
| D02 | P0 | Same Builder, `handleRun`: non-persistable/non-UUID IDs enter timed local simulation with random branch, 75–99% confidence and invented factors, followed by successful execution toast | The same Run affordance can produce a simulation presented as real execution. Restrict this branch to explicitly identified fixture/demo surfaces, or remove it from product routes. Keep useful layout randomness separate from runtime evidence. | A non-persistable product workflow cannot claim successful execution. Any intentional demo remains visibly labeled throughout its nodes, output and completion. |
| D03 | P0 | `components/gravitre/creative-grammar/index.ts`, `grammarToneForStepStatus`: completed/approved → verified. `app/runs/[id]/page.tsx` uses that result to render `EvidenceChip label="Verified"` | Completion and human approval are not source-of-record verification. Introduce separate display meanings, retaining raw reported status and verification provenance. Shared status *color* mapping alone is not the defect; the generated Verified label is. | A completed step says Completed; an approved gate says Approved. Verified requires an explicit verification contract/evidence. |
| D04 | P1 | `app/sources/[id]/page.tsx`: missing status defaults connected, environment defaults production, absent counts become zero, missing/invalid timestamps become Never. Schema/history failures default to empty arrays. `handleSync` ignores returned status and says completed. `app/sources/page.tsx` also ignores returned status before saying started. | The polished hub does not carry its truth rules into detail. Make detail a grounding workspace: lifecycle → reported schema/history → dependent agents/workflows. Represent unknown, loading, empty and failed independently. Interpret the actual sync contract before announcing success. | Sparse payload does not imply connected/production/zero/never. Real zero remains zero. Schema/history can retry without losing source context. Sync error/queued/completed display their returned meanings. |
| D05 | P1 | `app/settings/profile/page.tsx`, `activityStats`: literal 47 workflows, 156 approvals, 3 sessions | The personal profile claims fabricated activity. Remove unsupported metrics; active sessions can use the actual sessions response if its scope supports the count. Put identity, saved changes and session control ahead of analytics. | No static activity totals in product UI. Unknown is unreported. Counts identify user/org scope. |
| D06 | P1 | `app/intelligence/page.tsx`: `readNumber(summary.total_events, 0)`; `journey-rails.tsx` renders `String(totalEvents)`. Signal/map rails are independently stacked below the map at compact widths. Map has a 64vh minimum. | Absent evidence can appear as zero; on phone the reason and evidence may be distant from the selected relationship. Keep reported totals nullable. Recompose the investigation into selected relationship → why it matters → evidence disclosure, using existing canonical selection and inspector. This is a source-predicted geometry risk, not observed clipping. | Missing outcome totals remain unreported; real zero survives. At 390px a selected item gives immediate evidence access without hunting below unrelated rail content. At 834px chart/map and evidence remain usable. |
| D07 | P1 | `ai-workspace-provider.tsx` resets selection on route change. Selection publication exists in Activity, Approvals, Agents hub/profile, Connectors and Workflow detail. It is absent in manually inspected Goal detail, Assignment detail, Source detail and multi-agent selected-run journey; Training's generic Ask has no selected dataset/job publication | Deep work often loses its entity scope when asking AI. Add typed, minimal context for the selected goal/deliverable/source/job/run; visibly show scope and preserve the one runtime. Some entity kinds may require a contract extension rather than blindly adding a hook. | Asking about selected work carries its real ID and visible label; clear/back resets it. Draft/history survive presentation changes. No credentials/full sensitive payloads added to context. |
| D08 | P1 | `DepartmentNode` floats every non-reduced-motion node, including idle/resolved; `MapSatelliteNode` floats by emphasis; `SignalEdge` treats resolved as an animated edge | Motion is driven by graphic emphasis/status category rather than a finite event. This directly conflicts with Figma's no-ambient-floating rule. Use finite connect/transfer/resolve events; retain a restrained indicator only for genuine ongoing runtime work. | Idle, resolved and selected entities rest. A finished edge stops. Reduced motion remains static. One dominant work motion at a time, without deleting truthful loading/runtime feedback. |
| D09 | P2 | `TYPE.pageTitle`/`sectionTitle` and shared headers use font-sans; Marketplace/Intelligence bypass them for Space Grotesk. Final Carbon CSS uses ink #151618 and 5px control radius while comments claim sharp 8px; `Button` brand uses `bg-primary`, whose final light value is ink. `DATA_VIZ.secondary` uses g-signal (#4e7fcb) while g-viz-secondary uses Electric #315cff | Multiple token vocabularies remain active. Define role-level display/body, brand-commit, evidence, attention, geometry and motion contracts; preserve legitimate quiet graphite actions and semantic status variations. A named brand variant should not silently resolve to graphite. Do not make every action emerald. | Computed tokens and representative primitives match the chosen role in Figma. Display type comes from a shared role. Palette exceptions are documented; legacy aliases resolve consistently. Comments accurately describe final values. |
| D10 | P2 | Home renders an Ask line plus generic Ask button, lane Ask links and persistent helper. Training/Activity/catalog also add generic Ask. `LaneAsk` repeats the same “Ask” label across five lanes | Repeating entry points is not the same as an AI-native task model. Keep the global launcher, but make local actions specify intent: Explain this failure, inspect grounding, draft this plan. Remove redundant generic entry points when they add no scope or task. Home Ask line should visibly stage its prompt in the canonical workspace. | Each local AI entry has a distinct purpose and predictable staged/submitted behavior; no additional runtime. A keyboard and touch user can tell what context will accompany the question. |
| D11 | P2 | Profile uses blur glow, hover shadows and delayed 300–500ms reveal stacks, with no local reduced-motion hook or composition marker. Shared `StatCard` has unconditional Framer entry. Generic button sizes are 28–36px; the 44px CSS rule depends on coarse pointer and composition ancestry, excludes ordinary links, and portals may sit outside it | Quiet settings retain decorative dashboard styling. Some controls depend on page-specific patches for touch size/motion. Use plain identity/form/session sections and primitive-level safeguards where appropriate. This is a coverage risk, not a measured target violation across all devices. | Inspect computed hit areas at 390/834, including portaled windows and links. Reduced-motion preference prevents spatial entry animations. No halo decoration on personal settings. |
| D12 | P2 | Hand-written tablists in `OperatingFlow` and `OverviewLivingMap` have aria-selected but no local roving tabindex/arrow handling or explicit tab-panel association. Source delete has no pending exclusion | These controls need interaction quality, not new placement. Use accessible tab behavior or clearly labeled ordinary filter buttons. Lock destructive source submission/dismissal while pending and preserve failures. | Keyboard arrows/focus follow chosen tab semantics; screen reader identifies active content. Duplicate delete is prevented and focus returns after cancellation. |

## Composition brief: intentional variation

Do not apply a universal header → four KPI tiles → tabs → cards pattern. Nor should every non-discovery route become the same ruled list. Variation should reveal the work's structure.

| Surface family / routes | First question answered | Spatial/interaction direction | Compact experience |
|---|---|---|---|
| Home | What changed, what needs me, what should happen next? | Prioritized operating lanes and contextual command line; metrics support decisions | One relevant lane first, task switches, selected evidence; avoid duplicate Ask chrome |
| Marketplace, catalog, saved, org catalog | What outcome can I achieve with this? | Editorial outcome story, composition/dependencies and honest readiness; keep machinery behind preview | Outcome → prerequisites → install review; one dominant action |
| Plays | What work is available or underway? | Current operate rows are valid for running work; discovery/detail may use a compact topology explaining systems → agent → approval → result | Useful next step and required setup; keep business outcome separate from execution result |
| Intelligence, reports, predictive, metrics | What is changing, and why should I believe it? | Relationship/evidence investigation for Intelligence; analytical chart hierarchy for Metrics; reports/predictions retain their actual data structures | Reflow chart/legend; selected evidence next to the question; retain capabilities |
| Agents, identity/capability/knowledge/memory | Who owns this work and what can they actually do? | Identity + responsibility, capability relationships, grounding evidence; preserve real user photos, abstract signatures for system identity | Inspect specialist first; disclose configuration and grounding journeys rather than a wall of nested cards |
| Connectors, Sources, Environments | Can Gravitre rely on this system and data? | Connection lifecycle, health/freshness/schema, dependencies and repair path | Selected system sheet; nested detail retains truthful evidence and retry |
| Activity, Runs, Assignments, Approvals | What happened, where is it blocked, and what decision is mine? | Work queue → causal trace → evidence → scoped action. Approval continues the same path | One decision/exception at a time; readable trace and contextual dock above safe-area/navigation |
| Goals | What outcome are we pursuing and how far have we progressed? | Objective → saved proposal → milestones → measured result. Separate planning, execution and verification | One objective and its next milestone; linked builder handoff preserves saved proposal |
| Training, Model Studio, multi-agent | What should I prepare, run, inspect or assign? | Create progression for datasets/models; operate/evidence grammar for jobs and coordinated runs | Step/job-specific scope; selected inspector sheet; no synthetic sufficiency/progress |
| Workflow Builder | What will run, under whose authority, and what is missing? | Immersive graph, selected configuration and local Meson edits; truthful readiness and runtime trace | Sequence/selected-step configuration; expert canvas remains available; no falsely successful local simulation |
| Settings, permissions, enterprise/federation, billing | What configuration is stored, who may change it, and what happens on save? | Quiet setting rows, access matrix, partnership lifecycle, billing evidence; different structures for different contracts | Focused form/section, recoverable errors, explicit change scope; billing and grant review retain their own semantics |
| Marketplace publisher/admin/private/capabilities | What can be published, granted, reviewed or installed safely? | Separate creator progression, review queues, private bundle provenance and capability access | One review item/decision; disclose manifest/permissions/price evidence rather than decorate it |
| Marketing/auth/docs/onboarding/extensions | What does Gravitre do, and how do I start or reconnect? | Demonstrate the operating loop with concise real product explanation; auth task stays focused, docs remain readable | Single task and clear next destination; preserve error recovery and identity continuity |

Keep selection-origin windows, preserved parent drafts, honest partial failures, reported-versus-unknown values, reduced motion and the canonical runtime from the existing work. Model Studio and Schedule compact sheets are already wired; older handoffs describing them as unused are stale. Cursor's persisted goal plans, manual RAG ingestion, clearable policy fields and logo upload should remain part of the next verification scope, not be reimplemented from an old checklist.

## Completion sequence and review protocol

1. **Evidence integrity:** D01–D06. Correct claims before styling them. Add behavioral checks for sparse payloads, queued/failed sync, completion vs verification and local council acceptance. Owner-live evidence is separate.
2. **Token convergence and quiet materials:** D09/D11. Resolve final cascade/semantic roles once; then apply them to the manually reviewed primary/nested surfaces. Do not mass-replace status colors without preserving contrast and meaning.
3. **AI task scope and compact investigations:** D06/D07/D10. Give selection a meaningful question/action and disclose its evidence. Keep expert routes accessible and the same runtime/history/approval state.
4. **Motion and interaction:** D08/D12. Finite semantic motion, complete keyboard semantics, touch targets, pending/dismissal protections.
5. **Rendered family comparison:** obtain accessible current-head rendering, then walk primary → secondary → tertiary at 1440 / 834 / 390. Record route, SHA, viewport, state, screenshot and control outcome. Compare the five families side by side for intentional variety.
6. **Owner-live acceptance and CI:** real saves/install/export/ingest/delegation/delivery where authorized; distinguish queued from indexed and executed from verified. Inspect required checks on the current SHA independently. Billing E2E skipped remains skipped. Finance department and Compliance packs need agreed product scope. Slack/email destination delivery remains unverified. Merge/deployment are subsequent gates.

For each route, walk loaded, loading, empty, unknown, real zero, cached error, denied, selected and pending states as applicable. For each window, check title/scope, initiating control, initial focus, Escape/back/cancel, failed draft preservation, scroll containment, stacking, focus return and compact safe-area clearance. For charts, keep units, provenance, legends, tooltips and a usable narrow representation.

The static matrix names the next journey to validate; it does not mark it accepted. All 176 routes remain unverified visually at this head. Mixed compositions and aliases are intentional possibilities, not automatically defects. The next design pass should be assessed on whether users can understand the relationship between intent, systems, authority and measured work—not merely whether each page has the right token class.


## Implementation continuation — 2026-10-04

Implemented from `d5ae83d1` on the existing PR #298 continuation. The findings above describe the reviewed base; this section records corrections rather than rewriting that evidence. All 176 route rows remain **VISUAL_ACCEPTANCE = NOT_RUN**. Shared primitives affect many routes, but that is not individual journey acceptance.

| Findings | Implemented correction | Remaining acceptance |
|---|---|---|
| D01/D02 | Builder refuses execution for non-persisted IDs; removed its timed/random local product simulation. Council review no longer writes executed actions or manufactured confidence. Missing contributions/timeline stay unreported; more evidence links to an actual run when available. | Persisted save → run → real trace; council review, failures and approval behavior in rendered/owner-live sessions. |
| D03 | Shared grammar keeps completed, approved and verified distinct. Runs only generates the Verified chip for reported verification. | Verify actual execution and verification provenance independently. |
| D04 | Source detail preserves unknown lifecycle/environment/count/timestamp values and real zeros. Source hub/detail interpret failed, queued and completed sync responses. Source/schema/history retries preserve returned context. Test and removal have truthful failures, mutation exclusion and pending confirmation protection. | Owner-live connection/sync/removal, schema/query and workflow handoff; narrow tables/window focus. |
| D05/D11 | Profile is identity, saved changes and reported user sessions. Removed fabricated activity totals, glow tile and staged spatial reveals. Shared StatCard respects reduced motion. Primitive controls include mobile/coarse-pointer minimum targets, including portaled controls. | Computed targets, contrast, session control and focus at 390/834; shared links still require route-level target inspection. |
| D06 | Intelligence missing outcome count stays Not reported. Compact evidence appears before signals with native disclosures; existing map and selected inspector remain available. | Actual phone/tablet map → selected relationship → evidence journey and scroll geometry. |
| D07 | Goal, assignment/deliverable, source, dataset/job and coordinated-run journeys publish selected identity. Backend resolves the new kinds through existing org-scoped stores, minimal fields, source environment and deletion filters. Labels are bounded and remain untrusted page context; no added runtime or sensitive record body. | Canonical text/voice context continuity and owner-tenant authorization; isolated fake-query tests are not live RLS proof. |
| D08 | Removed unconditional floating from department/satellite nodes. Selection/emphasis does not start node spinning. Resolved/pending edges rest; actual routing/ongoing work retains feedback. | Rendered motion density, reduced motion and truthful ongoing state. Finite event choreography remains a design refinement. |
| D09 | Shared display roles use already-loaded Space Grotesk; body stays Inter. Carbon/frame/control geometry, emerald commit variant and Electric secondary data role align with reviewed Figma roles. Marketing creative brand uses the same Emerald value. | Computed cascade, contrast and exceptions across representative families; no claim every legacy raw color is converged. |
| D10/D12 | Home keeps a visible prompt-to-draft action and purposeful lane Explain actions; removed redundant generic header Ask. Training, Activity, catalog, goal and source entries specify a task using the same workspace. Hand-written incomplete tab patterns become ordinary pressed filter buttons. | Keyboard, touch, dismissal, draft retention and scope clarity on rendered primary/nested journeys. |

The regenerated source queue still identifies 176 routes and 364 control/disclosure files. The route matrix now records targeted implementation findings and remaining acceptance without marking unedited routes complete. Five families remain intentional: Discover chooses an outcome, Understand investigates relationships/evidence, Manage configures a capability, Operate advances reported work, and Create prepares a plan/model/workflow. Quiet Profile configuration is not another dashboard.

### Validation and limits

Final local checks on the implementation tree:

- Vitest `TZ=UTC`: **1,346 passed / 211 files**. Includes sparse/real-zero source evidence, returned failed/queued sync, cached retry, duplicate/failed removal and bounded selected-object payloads.
- Web `tsc --noEmit`: **exit 0**. Production `next build`: **exit 0**.
- Changed-file ESLint: **0 errors / 30 warnings**. Remaining warnings are existing unused declarations/hooks/navigation in the touched large modules; no new lint failure.
- Workspace-focus resolver: **13 passed**, using `--confcutdir=backend/tests/services`, fake scoped stores and isolated dependencies. Normal project fixture setup was blocked by missing global backend runtime dependencies (initially OpenAI, then Stripe); this is **not a full backend-suite pass**.
- Chat surface, user-facing status leak, intelligence customer surface and Gravitre brand guards: **PASS**. Cognitive structural guard: **PASS**, its Python import smoke/targeted pytest **skipped**, not passed.
- Inventory regenerated: **176 routes / 364 source files**. `git diff --check`: **pass**.

GitHub checks must be inspected on the published continuation SHA independently; prior-head checks do not establish current-head acceptance.

Current-head browser rendering remains blocked by `ERR_BLOCKED_BY_CLIENT` in the available browser. No valid capture or Figma pixel acceptance was obtained. Owner-live acceptance is not run. Finance department/Compliance catalog scope, Slack/email destination delivery and Billing E2E remain the previously documented open gates. Draft PR stays unmerged and not production-deployed; **IMPLEMENTATION_COMPLETE = NO; MERGE_READY = NO; CAUGHT_UP = NO**.


## Model Studio reference continuation — 2026-10-04

Based on published `79e03cb4`. Independent GitHub inspection at the start of this continuation found Web, Backend, runtime, dependency audit and Lighthouse passing; Billing E2E skipped. These results belong to that SHA, not the next continuation.

Model Studio now follows a preparation journey: provider metadata → access preview → purpose → existing target → acknowledged reference. It uses Create composition and a purposeful Plan model work entry to the canonical workspace. External datasets are not described as universally free or immediately usable models. A saved-reference ledger shows actual dataset, provider, purpose, target and access mode, without inventing import/index/readiness evidence.

Source review found three concrete gaps in this nested flow: duplicate writes/dismissal during save, invisible target/reference query errors, and acknowledged saves becoming failed saves when list refresh rejected. The implementation adds a synchronous mutation guard, frozen provider/dataset/purpose/target/segment while pending, independent loading/error/retry for targets and reference lists, and separate save acknowledgement from refresh outcome. Failed saves retain the selected review. Missing acknowledgement remains an error rather than an invented success. Refresh is independent after acknowledgement, so it does not trap the user in a completed write.

The shared SelectionInspector accepts opt-in pending state: compact close is disabled, Escape/outside dismissal is prevented, and ordinary dismissal/focus return resumes after the request returns. Other inspectors retain their existing behavior. This is contract/DOM-tested, not rendered viewport acceptance. Native controls and links retain minimum touch targets; no new backend endpoint, catalog promise or AI runtime was introduced.

Final checks and current-head CI are recorded with the publication handoff. The route matrix remains VISUAL_ACCEPTANCE = NOT_RUN, and owner-live save/authorization/materialization remain open. Draft stays unmerged and not deployed.


Model Studio continuation validation:

- Full Vitest TZ=UTC: **1,352 passed / 212 files**. New rendered-DOM behavior checks cover target retry, refused draft retention, pending duplicate/scope exclusion, acknowledged save with failed refresh, and saved provenance. Shared inspector checks cover disabled pending close/Escape and resumed dismissal. DOM checks are not screenshot acceptance.
- `tsc --noEmit`: **exit 0**. Production build: **exit 0** after discarding a corrupted generated Turbopack cache; the earlier cache failure was not a successful build.
- Changed-file ESLint: **0 errors / 0 warnings**.
- Intelligence customer surface, chat surface and whitespace guards: **PASS**.
- Independent GitHub jobs on parent **79e03cb4**: Web, Backend, Integration Smoke, runtime, dependency audit and Lighthouse **pass**; Billing E2E **skipped**. Inspect the next SHA separately.
- **VISUAL_ACCEPTANCE = NOT_RUN; OWNER_LIVE_ACCEPTANCE = NOT_RUN; IMPLEMENTATION_COMPLETE = NO; MERGE_READY = NO**. No merge/deployment.


## Cursor visual-blocker continuation — 2026-10-04 Vancouver

Based on Cursor's evidence commit `c8bbef64`, product head `0f058867`. Cursor reports current-head fixture coverage at 1440/834/390, with Home 834px clipping the At risk/Next lanes and AI capture failing after the imported `/ai` compatibility page navigated out of fixture auth. This is Cursor-reported partial visual evidence, not a fresh visual acceptance claim by this continuation.

Implemented two targeted corrections:

- Home's five minimum-width columns now apply at wide desktop only. Tablet uses two readable columns with Next as a full-width launch row; the next breakpoint uses three columns. Phone lane selection and the wide desktop template remain. Recapture 834px before declaring the clipping resolved visually.
- The AI fixture enters the canonical host in place, without the product `/ai` → `/home` redirect. ShotSurface provides the canonical host inside ShotAuthProvider. The outer host is suppressed only on enabled `/e2e/shots/` routes, preventing duplicate runtime mounts or rendering outside fixture auth. A two-case DOM test establishes one runtime under fixture identity and unchanged ordinary-route host mounting. Product authentication/redirect behavior is not bypassed or claimed owner-verified.

Local validation: **1,354 tests / 213 files passed**; typecheck/build **exit 0**; changed-file lint **0 errors / 0 warnings**; chat drift and whitespace **pass**. These checks do not establish screenshot geometry or real-owner AI behavior.

Cursor next: fetch the published correction, restart/rebuild with NEXT_PUBLIC_PLAYWRIGHT_E2E=1, recapture Home 834px and AI at 1440/834/390 on that SHA. Verify one runtime, named workspace, keyboard focus return, pending dismissal and reduced motion. Record the exact SHA/state/capture. Obtain an authorized owner session separately, then complete the original owner-live gates and current-SHA CI before merge/deploy. **MERGE_READY = NO** pending those gates; no merge or deployment performed here.


## AI canvas and connector return focus — 2026-10-04 Vancouver

Based on Cursor evidence commit `f96798dd`, preserving the 105630a0 recapture and Home 834 pass. Cursor reports AI landing below the first viewport (h1 y=1027), connector Escape focus falling to a script node, and Approvals leaving fixture auth. No merge or deployment occurred.

The AI fixture host is now inside the AppShell work canvas instead of a sibling after its full-height page. ShotSurface excludes its sibling host for the AI shot, preserving exactly one canonical runtime. A DOM assertion checks runtime containment in that canvas; a fresh screenshot is still needed to establish h1/composer visibility at 1440/834/390.

Connector row activation records the actual initiating button. The compact inspector restores that target on ordinary dismissal, including Escape when a pointer activation did not focus the row. Configure/reconnect transfer focus to their next destination instead of stealing it back. The existing desktop inspector stays inline. A regression check covers explicit row return after Escape/unmount.

Approvals' Decide handler performs local selection; no product navigation fix was invented. A mounted component test with fixture data checks Decide → review → Back without router calls or URL change. It does not reproduce or dismiss Cursor's browser-level fixture-auth exit. The next browser run must record the clicked element/nearest href, URL transitions, request initiators, console errors and auth/provider state to identify that exit.

Local checks: **1,357 passed / 214 files**; typecheck and production build **exit 0**; changed-file lint **0 errors / 6 existing warnings**; chat surface and whitespace **pass**. DOM/test identity is not owner-tenant proof.

Cursor next: rebuild the new product SHA with E2E enabled; capture AI inside the first viewport and repeat Connectors Escape/configure focus behavior. Trace the unresolved Approvals exit precisely. Exercise pending inspector dismissal through controlled, delayed fixture mutation responses and compare map/node motion with reduced motion on/off. Preserve these as fixture evidence. Owner-live remains blocked until an authorized session is available; **VISUAL_ACCEPTANCE = PARTIAL; OWNER_LIVE_ACCEPTANCE = NOT_RUN / BLOCKED; MERGE_READY = NO**. No merge/deploy here.

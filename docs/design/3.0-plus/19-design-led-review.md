# Design-led implementation review — 2026-10-04

Starting head: `72caac273010d564aa1e93d16dbfb458c0099ddc`, draft PR #298.

The user requested design leadership across primary, secondary and tertiary surfaces, with intentional variation rather than a repeated dashboard template. This record describes source inspection and implementation. It is not a completed visual audit.

## Design authority and composition

Re-read the creative integration, product UI grammar, interaction system and visual system documents. Retrieved high-fidelity Figma handoff `22:2` and its screenshot from file `OsDKeRy9HwfSKR3e9YyOFM`. Page-03 token provenance remains authoritative over older palette records. Figma describes foundation properties; these are not exported variable collections.

| Family | Composition to protect | Primary → secondary → tertiary review path |
|---|---|---|
| Discover | Outcome-led editorial hierarchy, browsing and comparison | Marketplace/Plays → package or Play detail → install, setup, permissions and confirmation |
| Understand | Evidence, relationships and functional visualization | Intelligence/Metrics → report/model/performance detail → attributes, filters, evidence and export |
| Manage | Identity, capability and connection context | Agents/Connectors/Sources → selected entity → configuration, authorization, schema and deletion |
| Operate | Scannable work, execution trace and actionable exceptions | Activity/Approvals/Assignments/Schedules/Lite → selected run/task/occurrence → decision, reschedule, delivery and confirmation |
| Create | Focused task progression with contextual configuration | Builder/Model Studio/Training/Settings → configuration step → selectors, previews, save/error and cancellation |

Shared tokens bind color, type, spacing, radius, elevation, focus and motion. They do not require the same arrangement on every page. Emerald indicates meaningful action/state; Electric supports analysis; Warmth supports attention. Space Grotesk display and Inter body remain the chosen typography. Keep chart libraries, evidence graphs, model attributes, KPI metrics and real capabilities.

The depth sequence remains canvas → inline/work content → selected context → floating surface → modal disclosure. Repeated decorative elevated cards should not replace operating rows or evidence structures. Desktop can retain adjacent context; tablet uses sheets; phone discloses one task with one primary action.

## Scope discovery

Run `python3 scripts/inventory-design-surfaces.py` to regenerate [the surface queue](18-design-surface-review-queue.md). Current discovery: 175 page routes; 108 product/legacy-product entries, 31 public/auth/support entries, 36 fixture/development entries; 362 reachable source files containing controls or disclosure JSX.

This inventory follows literal local imports and re-exports, includes ancestor layouts/templates/loading/error boundaries composed by Next, and records redirect expressions. Counts are source occurrences and static reachability, not visible controls or acceptance. Conditional tabs, permissions, computed imports, shared layouts and runtime-created controls still require a manual walkthrough. Existing route groups can produce duplicate route strings; source paths retain the distinction. Public, auth and fixture entries remain listed so they cannot silently disappear from scope.

## Source findings resolved in this pass

| Surface | Finding | Implemented behavior |
|---|---|---|
| Model Studio intent | Compact inspector stacked below the queue | Selection opens a tablet/phone sheet; desktop remains adjacent. Compact confirmation is inside the sheet, with a reopen action after dismissal. Continue closes disclosure before registration. |
| Model Studio dataset preview | Metadata and target form occupied the compact list; provider/search failures could look empty | Compact preview sheet retains parent-owned purpose/target state; loading, search/provider retry and inspect retry are explicit. Restricted datasets remain non-selectable. No new materialization API. |
| Model Studio reported values | Missing file count/progress became zero | Missing counts/progress remain unreported; actual zeros remain zero. Failed list loads do not simultaneously claim an empty registry. |
| Schedules detail | Unused sheet duplicated partial actions, while the live dialog omitted compact presentation | Compact sheet wraps the existing occurrence-aware content and actions. Desktop dialog remains. One-time/recurring timing, timezone, projected occurrence, reschedule, workflow editor and delete confirmation retain the same APIs. Removed the unused duplicate implementation. |
| Shared windows | Close targets below 44px; dialogs/confirmations lacked reduced-motion handling; sheet enter transition exceeded handoff UI range | Sheet/dialog close controls are 44px; all three overlay primitives honor reduced motion; sheet entry is 200ms. Selection inspector restores initiating control focus. |
| Lite tasks | Card stack, crowded actions, unknown status dereference, duplicate cancellation and missing progress | Compact operating rows; actions reflow below content on phone; unknown status remains unreported; cancellation shows pending and disables repeats; progress uses reported values. |
| Lite deliverables | Download action competed with long titles; fetch error looked empty | Ruled inventory rows with wrapping content, compact stacked download action, retry, pending download and reported file size. Existing download API retained. |
| Lite Results | Missing metrics became zero; fetch error looked like no results | Error/retry, preserved real zero, missing metrics unreported, stacked phone KPIs and ruled workflow/task evidence sections. Methodology/provenance retained. |

## Next review order

These are queued review targets, not accepted surfaces or presumed defects.

1. Goals list remains queued. Assignment creation, Assignment detail and Goal detail received the dated implementation passes below; execution trace, evidence, approval/edit/push windows and mobile geometry still require visual/owner-live acceptance.
2. Training/multi-agent remains queued. Agent identity/personality/capability/governance windows and knowledge add/source/expert-pack/retrieval journeys received the later dated pass below; responsive visual and owner-live acceptance remain.
3. Marketplace asset detail, installed/private/saved/sandbox/submit/publisher/org/platform admin: outcome hierarchy followed by machinery, installation/permission/billing depth and actual authority enforcement.
4. Workflows detail/builder/runs/failure prediction, Connectors/Sources nested pages and Integrations create/detail: contextual inspector selection, configuration windows, error recovery and real connections.
5. Settings nested permissions/profile/voice/billing/admin, AI composer/history/dock/fullscreen/mobile and legacy aliases: route-specific layout, navigation continuity, pending/error/permission state, focus and persistence.
6. Cross-surface visual comparison: primary and nested/disclosed states at 1440, 834 and 390; long names, missing fields, actual zero, loading, empty, cached error, permission denied, selected, streaming and pending mutation. Compare each family to its Figma target rather than forcing one page skeleton.

For every control: verify its label, action scope, disabled/pending behavior, accessible focus, target size, permission truth, success/error feedback and actual endpoint/navigation. For every window: verify entry/exit, title/description, scroll containment, focus return, back/escape/cancel, unsaved state, overlay stacking and reduced motion. For every data visualization: retain legends/tooltips and reported/unknown distinction across widths.

## Visual and live evidence limitations

The cloud browser returned `net::ERR_BLOCKED_BY_CLIENT` for `http://localhost:3055/e2e/shots/metrics`. The published preview fixture URL redirected to Vercel login. Neither is current product-screen evidence. No authentication credentials or access protections were changed. Source inspection and jsdom breakpoint tests establish implementation behavior; they do not establish rendered geometry or pixel parity.

`VISUAL_ACCEPTANCE = NOT_RUN`; `OWNER_LIVE_ACCEPTANCE = NOT_RUN`; `IMPLEMENTATION_COMPLETE = NO`; `MERGE_READY = NO`; `CAUGHT_UP = NO`.

Owner-live saves, installs, exports and delivery remain unverified. Organization logo upload, Slack/email delivery, Finance department and Compliance pack scope remain open. Billing E2E skipped remains skipped. Frontend permission controls are not proof of backend authorization. Draft PR #298 remains unmerged and is not production-deployed.

## Assignment and Goal detail continuation — 2026-10-04 UTC

Starting head `a388e0e7`. Assignment detail now uses a trace and ruled deliverable queue with adjacent desktop context and selection-driven compact sheets. Selection and assignment review are separate native buttons. Local per-deliverable approval markers were removed: review opens the assignment-wide decision flow; approved state derives from the API-returned handoff. There is no per-deliverable approval endpoint. Approval/rejection errors remain in the window; pending decisions cannot be dismissed. Explicit URL-opened review can be dismissed without deciding.

Primary-response editing and delivery remain on their existing APIs; recommendation previews do not expose those actions as applicable. Delivery is only announced when the destination returns `ok: true`. Cached refresh errors retain the current work, and failed execution does not hide returned output. Rejection copy confirms the saved decision without claiming agent notification. Self-reported confidence preserves zero, rejects invalid values and remains labeled unverified. Missing execution trace/progress stay unreported rather than synthesizing successful phases or a completion percentage. The existing shared result helpers remain unchanged for other surfaces. Timeline motion belongs to a running step; idle/success/failure/pending states do not loop.

Goals use a ruled progress band and ordered milestone sequence, with shared semantic tokens and typography. Missing progress/milestones remain unreported, actual zero remains zero, failed refresh retains cached evidence and long milestone titles/status badges reflow. Goal milestone state remains textual as well as colored.

This pass does not complete Assignments/new, Goals list or the remaining nested Agent/Model/Marketplace/Admin review queue. No rendered screen, pixel parity or owner-live acceptance is claimed.

## Assignment creation and nested Agent/Model continuation — 2026-10-04 UTC

Starting head `a8f0ef09`. This is a source review and implementation pass, with behavioral tests; no rendered acceptance is claimed.

| Surface | Purpose and implementation | Control/data behavior |
| --- | --- | --- |
| Assignment creation | Focused Create workspace: brief editor, ruled agent selection, horizontal compact step navigation and desktop step rail. Shared palette and display typography replace category-colored selection cards. | Real connector inventory replaces hard-coded connected systems. Unknown/inactive connections cannot be selected. Brief starters insert usable text; whitespace fails validation. Destination/output/approval choices are disclosed requests, not claims of delivery or authorization. Returned job opens immediately after submission; duplicate pending submission is blocked and failure preserves the review. Existing job/context API fields retained. |
| Agent profile and capabilities | Manage identity and access: capability read/write groups remain distinct; allowed connector scope comes from the capability API. | Permission names no longer masquerade as connected systems. Missing statistics remain unreported; real zero survives. Cached profile/access remains available after refresh failure, with retry. Missing execution permission does not imply a proven advisory restriction. |
| Agent knowledge | Manage grounding: existing source, expert pack, instruction and retrieval composition retained. Compact instruction actions reflow and tabs honor reduced motion. | Independent fetch errors/retries, loading versus empty instructions, retained cached evidence. Counts stay unreported until assignment data returns. Removed manufactured ingestion progress based on record count; zero document count remains zero. Instruction delete waits for the API and retains the confirmation on failure. |
| Agent memory | Ruled evidence rows instead of hovering cards and confidence rings. Provenance, reported confidence, usage and dates are explicit; actions stay visible on touch devices. | Real zero versus unknown preserved. Error/retry and cached rows; no false empty after failure. Editor validates confidence, retains failed drafts and cannot dismiss during save. Delete confirmation persists on failure; successful deletion clears it. Existing memory APIs retained. |
| Agent chat | Scoped handoff to the existing canonical AI workspace. | Fetch/retry and cached-agent behavior added; no second runtime. Restore action has a 44px target. |
| Registry model detail | Existing model insights, lifecycle, configuration, versions and inference preserved. | Model/connection errors retry independently, cached model retained, unknown connection evidence disclosed. Inference validates a nonempty array of objects before calling the API. Deploy checks returned `ok` before announcing acceptance; zero latency remains reported. Reduced-motion entry and accessible input/error labels. |
| Built-in model detail, including `/models/built-in/[name]` alias | Understand evidence: existing overview/performance/readiness/impact tabs and model guidance retained. | Catalog loading and genuine absent-model state; per-evidence retry. Missing readiness gate/samples/outcome counts are unreported; zero confidence remains zero. Missing advisory policy does not become "No". Training is announced as an accepted request and refreshes reported state. |

Creation and memory rows are extracted from route modules for reuse and meaningful component tests. Fixture knowledge state was updated to the hook contract. The static inventory remains an aid to review, not an acceptance record.

Remaining nested review includes identity/personality editors, capability/governance configuration windows, knowledge add/expert-pack/retrieval journeys and Training/multi-agent. The broader queue still includes Goals list, Marketplace/admin, Workflows/Builder/run detail, Settings and AI workspace states. Every changed and remaining route still needs the rendered 1440/834/390 state matrix and appropriate owner-live mutations. The previously documented browser/preview access limitations remain unresolved.

## Deeper Agent configuration and knowledge journeys — 2026-10-04 UTC

Starting head `8acd5829`. This continuation reviews the actual nested editor and knowledge components and their API contracts. It establishes source and behavioral evidence, not rendered geometry or owner-live acceptance.

| Journey | Design and behavior implemented |
| --- | --- |
| Identity window | Focused, scroll-contained dialog with an identity preview and explicit photo persistence. Uploading no longer resets name/department/icon drafts after cache refresh. Original department values are retained. File type/size validation, inline errors, mutation exclusion and dismissal locks preserve failed edits. Photo changes save immediately; Cancel applies to the remaining edits. |
| Personality | Ruled setting rows, native response-style radios and semantic selection tokens. Drafts stay intact through background refresh; discard and saved baseline remain explicit. Save failure stays inline and concurrent editing is locked during persistence. |
| Voice library/design | Existing library, preview, design and save endpoints retained. Library failures retry; generation/save errors retain existing takes. Preview has a Stop action, remains pending during actual playback and releases audio/object URLs on end/unmount. Stopped pending previews cannot start later. Custom-save duplicates are blocked; library creation is distinguished from agent personality persistence. |
| Capability configuration | Accessible pressed state, wrapping custom labels, minimum touch actions and clear configuration versus runtime authorization wording. Save preserves connector/guardrail names outside the catalog. Drafts survive background refresh, errors stay inline and discard restores the persisted baseline. Retained extra labels remain visible. |
| Execution policy | Admin-gated dialog on the existing `agentIdentityApi.upsert` API, with stored trust level and daily ceilings. Backend PUT is already protected by `require_admin` and agent/org assertion. The UI preserves tool/action/data scopes, delegation settings and approval overrides because the PUT model initializes absent arrays. Zero limits survive; invalid numeric limits fail locally. Existing limits cannot be cleared through this API, and the form says so. Organization policy/active delegations remain authoritative. |
| Governance evidence | Identity/capability/snapshot failures retry. Missing data is unreported rather than a configured policy or an empty permissions set. Explicit effective action/pattern arrays take precedence over stored arrays. Phone policy summaries stack; policy saves refresh the reported evidence. |
| Add knowledge | Source-versus-expert-pack choice uses a ruled navigation sheet. Existing library closes the sheet and selects Sources; expert-pack choice selects that tab. Upload and connector choices are disclosed library/configuration handoffs. Unsupported native text creation stays unavailable. |
| Source assignments | Ruled operational inventory with all sources reachable through Show more. Loading/error states do not imitate an empty library. Sync checks returned `success`; failed sync cannot announce success. Removal confirms its agent-only scope and retains a failed decision. Global assignment/removal locks and disabled menu actions prevent overlapping mutations. Legacy config assignments do not expose an unsupported removal action. |
| Expert packs | Contextual discovery cards retain availability and assigned state. Catalog fetch has retry and truthful empty state; recommendations are attributed to the catalog rather than invented from agent skills. Assignment controls account for pending knowledge mutations. |
| Retrieval | Evidence-first question form, reported match count/assignment scope, missing assignment list and expandable full excerpts. Failed subsequent queries retain previous evidence and its original query label. Zero matches means no returned matches, not absent telemetry. Invalid/missing relevance stays unreported; actual zero remains zero. |

The broader review queue now proceeds to Training/multi-agent, Goals list, Marketplace/admin and remaining Workflow/Builder/run and AI workspace states. Delegation administration and more granular policy scope/override editing remain outside this form. Native text knowledge creation and clearing existing policy ceilings remain unsupported by the exposed contracts. Rendered viewport/Figma and owner-live acceptance remain required for this pass and all prior passes.

## Training and multi-agent journeys — 2026-10-04 UTC

Starting head `8da69b5d`. The review covers the Training route and its dataset preparation, job monitoring, instructions, model assignment and destructive confirmations; the canonical multi-agent route, roster/start dialog, run inspector, council evidence and subtask result disclosures; and the legacy swarm redirect. Findings are based on source/API contract inspection and component behavior checks. No rendered viewport or owner-tenant acceptance is established by this pass.

| Surface and level | Design and behavior implemented |
| --- | --- |
| Training — primary | Create composition remains preparation-led, with separate Datasets, Jobs, Instructions and Fine-tunes sections. Prompt guidance no longer sits beneath a fine-tune label. Shared display/body roles and touch targets are used; loading and failed initial requests cannot become empty libraries or zero counts. Freshness is stamped on successful fetches. Workspace setup catches failures. |
| Dataset preparation — secondary | Ruled inventory retains dataset type/status/count/date evidence. Example input/output, bulk material and document fields have accessible names. Each dataset's draft survives closing or switching preparation panels in this mounted journey. Native file selection has batch validation, caught asynchronous read errors and a pending lock before reading begins. Bulk import reports every malformed nonempty line and imports nothing until corrected. Returned API counts drive import messages. |
| Dataset creation and starter material — secondary | One synchronous mutation exclusion guard prevents overlapping mutations and locks preparation fields while persisting. Failed forms remain editable with inline errors. A starter dataset ID is retained after creation so a failed record import retries into that dataset rather than creating another. This does not provide backend idempotency or guarantee duplicate-free record retries after an ambiguous network response. |
| Jobs and destructive windows — secondary/tertiary | Only finite reported progress in the 0–100 range creates a labelled progress gauge; actual zero survives. Ambient shimmer is removed; reduced motion is honored. Reported errors, accuracy and loss remain visible, including zero metrics. Creation is announced as a requested job, not completed training. Dataset/instruction deletion and job cancellation use scoped confirmation dialogs that retain failed decisions and block pending dismissal. |
| Instructions and assignment — secondary | All agents remains an explicit instruction scope and is no longer replaced by the first roster entry. Agent/model option errors retry. Assignment requires an explicit model choice; base-model clearing is a distinct action and a real null payload. Missing fallback-agent assignment data is not synthesized as a known clear assignment. Existing training, instruction and assignment APIs are retained. |
| Multi-agent history — primary | Operate composition uses ruled selectable rows and explicitly recent-run counts from the latest 30 requested rows. Unfetched counts are unreported. No reserved desktop inspector column appears before selection. Workspace/list errors retry and cached rows remain visible after refresh failure. Motion is short and reduced-motion aware. |
| Multi-agent start — secondary | Focused objective/coordinator/decision form with numbered work splits and visible editable agent roles. Roster suggestions wait for agent and pack-preference loading; failed pack preferences do not prevent choosing available workspace agents. Unknown or absent agents cannot become valid selections. Every displayed subtask must be complete or removed, preventing silent partial dispatch. Stable row IDs, 44px controls, inline errors, synchronous exclusion and a dismissal lock retain failed setup. The start payload and existing dispatch API are unchanged. |
| Run inspector — secondary | Desktop context sits alongside history; tablet/phone use the shared selection sheet. Switching selections resets local run controls. Existing recommendations and subtask evidence stay visible when refresh fails. Aggregate/cancel use returned API state without requiring another successful fetch; a failed aggregate response cannot announce a recommendation. Cancellation is a retained scoped decision, and pending actions block closure/selection changes. |
| Council and subtask evidence — tertiary | Confidence is labelled a council estimate, distinct from execution verification. Missing subtask evidence is unreported, not zero contributions. Full reported recommendation/result disclosures retain content omitted from readable summaries. Unknown run/subtask statuses are unreported rather than pending/queued. Shared contribution chrome is neutral and unelevated. The explanatory convergence diagram remains, with an illustrative label and no ambient particles. |

Existing charts, runtime execution, voting methods, APIs and backend authorization are preserved. These tests do not establish live provider fine-tuning, tool execution, permissions or tenant saves. The 1440/834/390 loading/error/selected/pending/permission matrix and Figma page-03 comparison remain NOT RUN because the previously recorded preview/browser access blockers remain unresolved. Owner-live training and multi-agent actions also remain NOT RUN.

The source review queue proceeds to Goals list, Marketplace/admin and remaining Workflow/Builder/run and AI workspace states. Implementation completion, merge readiness and caught-up status remain NO until the broader queue and acceptance gates are completed.

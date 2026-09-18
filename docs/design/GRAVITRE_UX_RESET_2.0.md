# GRAVITRE UX RESET 2.0

**Status:** Cesar **design selections recorded 2026-09-18**. Phase A–H shipped. Phase I Approvals **queue + one primary CTA** on `/approvals`. Remaining hubs remain later.

**Do not** reopen one-runtime architecture unless a regression is evidenced.

**Do not** reopen one-runtime architecture unless a regression is evidenced.

---

## Cesar selections (locked)

| Surface | Selection | Binding amendment |
| --- | --- | --- |
| Nucleo | Sharp 24 Outline | 14 / 16 / 18 / 20 / 24 as specified. Function glyphs. No `AiOutline24` as AI identity. No Lucide purge. |
| Connectors | **B Discovery → Management** | Available = compact logos. Connected = dense list. Topology optional. No restore-list task. |
| AI | **B Command OS** | Grammar: Conversation → Command → Work → Inspect. Conversation is the persistent spine, **not** a disposable log. Work is primary only when a real artifact/execution exists. Inspector only on selection. No empty inspector. No permanent task rail. |
| AI compact | header + conversation + composer | No rails, no empty work pane. |
| AI expanded | conversation primary; work beside when active; optional collapsible history | Do not replace conversation when work opens. |
| AI fullscreen | conversation + work canvas + conditional inspector | Continuity of the same thread. |
| Mobile AI | conversation first; work/inspector as focused sheets | Do not shrink desktop columns. Voice = composer state. |
| Agents | **B Operating Team** | TEAM default. LIST + GRAPH remain. Nucleo role identity. One Intelligence Core. |
| Relationships | **C Graph + Evidence Workspace** | Graph primary. Evidence on selection. Search/focus/filter/zoom/pan/pin/neighborhood/path. Explain **why**. |
| Performance | **C Diagnostic Workspace** | Outcome → contributing stages → span → evidence. Pipeline/waterfall subordinate. Real instrumentation only. |
| Workflows | **C Intent + Orchestration** | Outcome statement, then canvas. Config via inspect, not hidden behind Ask. TRACE overlay. |
| Runs | **C Outcome/Evidence default**; **B Trace** as drill-down | Result first, then inspect trace. |
| Inspector | Shared principle | No selection → no inspector. |
| Motion | State vocabulary | EXPAND FOCUS TRACE REVEAL RESOLVE CONNECT EXECUTE. Reduced motion. |

**Harness:** `/dev/ai-workspace-preview?s=&scene=` · **Canvas:** `gravitre-ux-reset-2.canvas.tsx` · **Shots:** `e2e/artifacts/ux-reset-2-review/`

**Production UI changed this slice:** Phase I queue + inspect on `/approvals` (select to decide; Approve is the primary CTA; Reject is secondary). No invented prices or Enable toggles.

---

**Evidence class:** repository read of `apps/web` + UX Reset 1.0 phase reports (1A–7 + live-proof) on 2026-09-17. Source PASS ≠ production PASS. Authenticated gravitre.app click-through remains **NOT PROVEN** except where separately recorded.

**Companion docs:**  
`GRAVITRE_NUCLEO_ICON_SYSTEM.md` · `GRAVITRE_MOTION_SYSTEM.md` · `GRAVITRE_PRODUCT_VISUAL_SYSTEM_2.0.md`  
**Board:** Cursor canvas `gravitre-ux-reset-2.canvas.tsx`

**1.0 rule remains in force until 2.0 is approved:** `.cursor/rules/gravitre-ux.mdc`

---

## A. UX Reset 1.0 reconciliation

Requirement-by-requirement. Status vocabulary: **COMPLETE** (source architecture or IA as specified) · **PARTIAL** · **NOT STARTED** · **SUPERSEDED** · **NO LONGER APPLICABLE** · **NOT PROVEN** (code exists; live authenticated not shown).

Layers are called out separately: Architecture / Interaction / IA / Visual / Motion / Responsive / A11y / Polish.

### Runtime and presentation

| REQUIREMENT | ORIGINAL INTENT | CURRENT IMPLEMENTATION | STATUS | CODE EVIDENCE | ROUTES | WHAT REMAINS | 2.0 DISPOSITION |
| --- | --- | --- | --- | --- | --- | --- | --- |
| One `useChat` owner | Kill Ask + agent-chat runtimes | `AiWorkspace` sole `@ai-sdk/react` `useChat` (~L584) | **COMPLETE** (architecture) | `app/ai/_components/ai-workspace.tsx`; Phase 1A tests | `/ai`, float, agent chat, Ask | Hoist to provider optional | Keep; visual 2.0 on same owner |
| Ask is summon, not chat | No third runtime | `AskGravitreComposer` → `summonWorkspace` | **COMPLETE** (architecture) | `ask-gravitre-composer.tsx` | Intelligence + header Ask | — | Keep |
| `AskGravitreEntry` | Summon, don’t navigate | Still `<Link href="/ai">`; unused by Intelligence | **PARTIAL** / orphan | `ask-gravitre-entry.tsx` | none live | Delete or convert | Remove as product |
| Agent chat = scoped presentation | Keep route, one runtime | `agents/[id]/chat` summons fullscreen | **COMPLETE** (architecture) | `app/agents/[id]/chat/page.tsx` | agent chat | Live model stream **NOT PROVEN** | Polish identity; keep route |
| Presentation names | MINIMIZED/COMPACT/EXPANDED/FULLSCREEN | Canonical map; React still `helper`/`float` | **COMPLETE** (mapping) | `gravitre-ai-presentation.ts` | all AI | Rename state later if tests allow | Keep mapping |
| `/ai` = fullscreen same instance | Not a second embed | Auto-open fullscreen when float on | **COMPLETE** (architecture) | `ai-workspace-provider.tsx` | `/ai` | Prod session **NOT PROVEN** | Visual 2.0 empty/active |
| `/assistant` redirect | Preserve deep link | Redirect | **COMPLETE** | `app/assistant` | `/assistant` | — | Preserve |
| Kill-switch XOR | Flag-off page-local workspace | `GRAVITRE_AI_FLOAT_ENABLED` | **COMPLETE** (intentional) | `ai-workspace-flags.ts` | `/ai` | Keep rollback | Out of 2.0 visual; keep |
| AuthGate | Unmount AI logged out | `GravitreAIAuthGate` | **COMPLETE** (architecture) | `ai-auth-gate.tsx` | app shell | Real Supabase logout **NOT PROVEN** | Preserve |
| Restore on launcher | Don’t new session | `restoreFromHelper` | **COMPLETE** (source) | `ai-helper.tsx`, provider | all | Prod **NOT PROVEN** | Motion: dock, not morph |
| Query params | `c` `m` `prompt` `mode` | Still on `/ai` | **COMPLETE** (source) | `app/ai/page.tsx` | `/ai` | Live **NOT PROVEN** | Preserve |
| Conversation persist across routes | Same host | Provider + host | **PARTIAL** / **NOT PROVEN** live | host + 1B report | all | Prod proof | Keep |
| Voice same workspace | Don’t remount STT | `useVoiceDuplexSession` in `AiWorkspace` | **COMPLETE** (architecture); hardware **NOT PROVEN** | `ai-workspace.tsx`, `voice-presentation.tsx` | AI | Hardware STT/TTS | Visualizer already canonical; no new orb |
| Tools persist resize | Don’t cancel | Same owner; mocked stream 1B/live-proof | **PARTIAL**; live READ **NOT PROVEN** | live-proof spec | AI | Live tools | Keep |
| `workspace_focus` | First-class selection | Typed FE + backend | **COMPLETE** (contract) | `gravitre-workspace-focus.ts`, schemas | Ask surfaces | Live audit_events **NOT PROVEN** | Keep |
| Contextual Ask on hubs | Don’t copy-paste context | Phase 5 `setSelectedEntity` / header Ask | **COMPLETE** (IA chrome) | Phase 5 report | home, agents, workflows, connectors, approvals, activity, marketplace, training, models | Settings not in scope | 2.0: infer more, fewer filters |
| Intelligence command bar | In-page composer | Intentionally kept; not second `useChat` | **COMPLETE** (kept) | `intelligence-command-bar.tsx` | `/intelligence` | Unify visually with Ask | Keep as command surface, Nodus polish |
| Meson not chat | Preserve | Unchanged | **COMPLETE** | Meson toolbar | workflows | — | Preserve |
| Marketing isolation | Preserve | Unchanged | **COMPLETE** | marketing app | `/` | — | Preserve |
| `dev/ai-workspace-preview` | One design harness | **Promoted** to UX Reset 2.0 design exploration (`noindex`, mock data, no second `useChat`) | **COMPLETE** as harness home | `app/dev/ai-workspace-preview` | `/dev/ai-workspace-preview` | Cesar selects concepts here | Do not add preview-v2 |

### Visual / IA (1.0 plan items 4–6)

| REQUIREMENT | ORIGINAL INTENT | CURRENT | STATUS | EVIDENCE | ROUTES | REMAINS | 2.0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Empty AI | Identity + composer + text suggestions | Phase 2 removed card grid / mode pills | **COMPLETE** (IA); visual still generic SaaS | Phase 2; `ai-workspace.tsx` empty hint | `/ai` | Sophistication | Prototype 1–2 |
| Compact no rails | Default compact | Compact has no history/inspector rails | **COMPLETE** (IA) | Phase 2 | float | Depth/motion polish | Prototype 3 |
| Expanded rails collapsed by default | Progressive | Defaults collapsed; toggles remain | **COMPLETE** (IA) | Phase 2 | expanded/fs | TaskSidePanel + LiveActivityRail still rails | Inspector language |
| Message chrome | No giant cards | User bubble no drop shadow; still chat bubbles | **PARTIAL** (visual) | Phase 2 | AI | Premium transcript | AI 2.0 polish |
| Sources / execution / artifacts | After answer | `<details>` in transcript (Phase 7) | **COMPLETE** (IA disclosure); **PARTIAL** (rails remain) | `assistant-source-links.tsx`, `chat-execution-panel.tsx`, `task-side-panel.tsx` | AI | Contextual inspector vs sticky panel | Artifact workspace |
| Agents list/team/graph | Find teammate | TEAM default; department coworkers; Nucleo role marks; inspector on selection | **PARTIAL** (Phase C started); avatars still on identity editor | `agents/page.tsx`; `DEFAULT_AGENTS_FLEET_PREFS.view === "team"` | `/agents` | Live session **NOT PROVEN** | Operating Team |
| Agent profile | Text sections | Text nav + totals disclosure | **COMPLETE** (IA) | `agents/[id]/page.tsx` | detail | Surface vs card residual | Polish |
| Relationships graph-first | Graph hero | Graph default; evidence inspector only on selection; Focus/Pin/Neighborhood | **PARTIAL** (Phase D started) | `relationships-workspace.tsx`; graph default in `use-relationships-workspace.ts` | learning relationships | Live session **NOT PROVEN** | Evidence graph |
| Performance pipeline | Metrics → pipeline → trace | Diagnostic: Outcome headline, contributing stages, inspector on selection, metrics disclosure, contribution rows; waterfall omitted without span telemetry | **PARTIAL** (Phase E started) | `performance-stage.tsx`; `outcome-attribution-flow.tsx` | `/intelligence/performance` | Live session **NOT PROVEN**; no instrumented duration bars yet | Performance 2.0 |
| Settings rows | Not card-per-field | Many preference rows flattened; orgs page still cards; residual bordered groups | **PARTIAL** | `settings/page.tsx`, `settings/organizations/page.tsx` | settings | Document model | Settings 2.0 |
| Connectors compact | List default; topology opt-in | Discovery compact logos then management dense list; topology opt-in; inspector on selection. `viewMode` key still `"grid"` for the list branch. | **PARTIAL** (Phase H started) | `connectors/page.tsx`; `available-connectors-strip.tsx` | `/connectors` | Live **NOT PROVEN**; detail page still card-heavy | Connectors 2.0 |
| Connector detail | Flatten | ~26 shadcn Cards | **NOT STARTED** (1.0 leftover) | `connectors/[id]/page.tsx` | detail | Document/split | 2.0 |
| Workflows table-first | Find/run | Table default all widths (Phase 7) | **COMPLETE** (IA) | `workflows/page.tsx` | `/workflows` | Builder Badge density | Workflows 2.0 = canvas |
| Workflow builder | Not tab-first | Canvas primary; intent statement above canvas; config via Inspect sheet; TRACE overlay (path emphasis, no invented timings) | **PARTIAL** (Phase F started) | `workflows/[id]/builder/page.tsx` | builder | Badge density; live **NOT PROVEN** | Workflow 2.0 |
| Workflow detail | Flatten | ~28 Cards | **NOT STARTED** | `workflows/[id]/page.tsx` | detail | — | 2.0 |
| Activity list | No KPI wrap | Two-pane; KPI wrap removed; inspector on selection; TRACE via run `?trace=1` | **PARTIAL** (Phase G started) | `activity/page.tsx`; `/runs/[id]` | activity, run detail | Live session **NOT PROVEN** | Runs 2.0 |
| Marketplace tiles | Keep discovery | Intentionally kept PriceBadge/tiles | **COMPLETE** (kept) | marketplace assets | marketplace | Operational vs discovery | Marketplace 2.0 |
| Training / models text nav | No pill tabs | Phase 6–7 text nav | **COMPLETE** (IA) | training, models, model-studio | those | Expert workspace polish | Models/Training 2.0 |
| Intelligence hub I11 | 7 text links, no Training | Shots **PASS**; live login **NOT PROVEN** | **COMPLETE** (chrome); **NOT PROVEN** live | `intelligence-hub-tabs.tsx` | intelligence | Visual intelligence | Intelligence 2.0 |
| Home widgets | Keep modular | Kept | **COMPLETE** (kept) | `home-dashboard.tsx` | `/home` | Visual upgrade, no card-in-card | Dashboard 2.0 |
| LearningSurfacesCallout | Flatten | Gradient removed; text links | **COMPLETE** (IA) | `learning-surfaces-callout.tsx` | training | — | Keep |
| No decorative Three.js on product | Hard stop 1.0 | No R3F; isolated WebGL on intelligence marketing-ish viz | **COMPLETE** / watch | package.json; webgl files | intelligence | Don’t expand | 2.0: 3D only if justified |

### Motion (1.0 item 7)

| REQUIREMENT | STATUS | EVIDENCE | 2.0 |
| --- | --- | --- | --- |
| Same physical workspace morph | **COMPLETE** source; **NOT PROVEN** prod | Phase 4 + live-proof harness | Formalize vocabulary; minimize still dock |
| Product-wide motion language | **NOT STARTED** as system | Random durations remain in 194 framer files | Motion system doc |

### Themes from 1.0 §2 (architecture vs design)

| Theme | Architecture / IA | Visual / interaction design |
| --- | --- | --- |
| No card-first | Many hubs flattened | Connector grid default, sources tiles, org cards, contribution cards remain |
| No card-in-card | Reduced | Dashboard widgets still nested internally |
| No tab-first | Hub text links | Memory `TabsList`; enterprise pill nav |
| No pill explosion | Reduced | Builder badges; status chips justified |
| One primary action | Partial | Many hubs still 3–6 equal buttons |
| Hierarchy without boxes | Partial | Hairline + type; still boxed settings |
| Nucleo functional | AI chrome | Lucide ~306 files |
| Subtle hover / meaningful shadows | Tokens exist | Elevation + glow tokens overused risk |
| One AI workspace | Yes | Experience still template chat |
| Progressive disclosure | `<details>` | Inspectors not one language |
| Data density | Improved on tables | Headers still tall in places |
| AI reduces UI | Ask on hubs | Filters still dominate catalogs |
| Nodus authority | Tokens | Pages still shadcn-default |
| Mobile / a11y / responsive | Helper in viewport 1B | Recomposition not designed |
| Graph-first relationships | Map exists | Graph UX unfinished |
| Voice in workspace | Yes | Hardware unproven |

### What 1.0 only audited (never implemented as visual system)

ChatGPT / Perplexity / Manus **principles** in 1.0 §K–M: extracted, not cloned, **not** a finished AI visual language. Wireframes lived on the 1.0 canvas — **prototyped, then partially implemented** (empty/composer flatten), not the 2.0 sophistication pass.

### What no longer makes sense

- Treating **three `useChat` instances** as current topology (superseded by 1A).
- Inventing a `/relationships` product if Intelligence map is the graph (keep graph-first there; optional dedicated route is 2.0 product choice).
- Folding Meson or marketing chat into the workspace.
- Using 1.0 “minimum” as **plain white + gray border + card**.
- Adding Aceternity/21st dumps as visual authority.

### What moves to 2.0

Visual grammar, semantic Nucleo (not file-count), motion vocabulary, per-surface models, leftover card pockets, connector discovery vs management, inspector language, agent identity, Playwright visual regression, production proofs. See A–Q.

---

## B. Completed work (1.0)

Phases 1A–7 + live-proof harness on `main` (deployed frontend historically `dpl_9Sgmgc2W1MP7165H2VyedEM5hQj7` @ `f8960857`). One runtime, presentation map, context contract, Ask summon, agent-scope, IA flatten on named hubs, `<details>` disclosure, shared `layoutId` morph (harness).

---

## C. Partial work

Task/activity rails; connector default grid; settings/orgs/connector-detail/workflow-detail cards; Memory tabs; Performance contribution cards; Lucide majority; agent avatars; production proofs; `AskGravitreEntry`; preview route.

---

## D. Unimplemented work (1.0 visual sophistication + 2.0)

Premium tables/lists; spatial models per route; Nucleo taxonomy completion; motion vocabulary beyond AI frame; reduced-motion product QA; visual regression matrix; custom viz for runs/approvals/performance; icon containers removed; agent identity redesign.

---

## E. Superseded work

Pre-1A triple `useChat` diagram. Prototype `layoutId="gravitre-ai-window"` superseded by `gravitre-ai-workspace-frame`. Phase 3 “connectors default list” **superseded in code by grid default** (treat as regression, not a new product decision unless Cesar confirms grid).

---

## F. Route inventory

See § route-by-route below and canvas **Routes** tab. Notable: `/runs` → `/activity`; `/search` = chat search; no product `/relationships`; research/tools/artifacts are in-thread.

---

## G–M. Debt

**Complexity:** `ai-workspace.tsx` ~3k LOC; workflow builder ~6.6k; connectors page ~3.4k.  
**Visual:** Lucide + Phosphor + Nucleo; glow tokens; card pockets listed in C.  
**Icon:** Nucleo map ~28 keys vs required taxonomy.  
**Motion:** 194 framer files; tokens exist but not enforced.  
**Interaction:** Equal-weight buttons; inspector inconsistency.  
**A11y:** primitives exist; icon-only and contrast not globally proven.  
**Responsive:** 1B viewport launcher; pages not recomposed.

---

## N. Visual grammar

Typography, surfaces, depth, Nucleo, color, motion, selection, focus, connection, execution, status, progress, error, success, inspection, AI context — see visual + motion + nucleo docs. Consistency = those tokens, **not** identical page skeletons.

---

## O. Layout system

Per-route model (target):

| Route | Model |
| --- | --- |
| `/home` | WORKSPACE + modular widgets |
| `/ai` | COMMAND SURFACE + conversation |
| `/agents` | LIST / TEAM / GRAPH |
| `/agents/[id]` | DOCUMENT + DETAIL |
| `/workflows` | TABLE |
| Builder | CANVAS + FLOW |
| `/connectors` | LIST + optional GRAPH |
| `/activity` `/runs/[id]` | SPLIT + TIMELINE |
| `/approvals` | QUEUE |
| `/intelligence` | GRAPH + INSPECTOR |
| Performance | PIPELINE + TRACE |
| Settings | DOCUMENT |
| Marketplace discovery | TILE (justified) |
| Marketplace installed | LIST / operational object |

---

## P–S. Nucleo / motion / effects / depth

See companion docs. Depth levels 0–4. Effects: hairline, selection, local tint. No neon OS.

---

## T. Page-by-page target architecture

Dashboard 2.0–Settings 2.0 as specified in the program brief (widgets justified; agents workforce; workflows orchestration; relationships graph hero; performance diagnostic story; runs trace; approvals queue; connectors ecosystem; intelligence map; settings document; marketplace discovery≠ops).

---

## U. Prototype inventory

Canvas tab **Prototypes**: AI empty/active/compact/fullscreen; Agents team/list/graph; Relationships graph+inspector; Performance pipeline+trace; Workflow canvas; Run detail; Connector management; Approval queue; Settings; Mobile AI/agents/relationships. **Diagrams, not production.** Motion described as state pairs (canvas SDK has no Framer).

---

## V. Component reuse

Keep: `AiWorkspace`, AuthGate, provider, Nucleo semantic, `TYPE`/`MOTION`/`SEMANTIC`, Intelligence/Agents hub text nav, table-first workflows, Ask summon, VoiceStateVisualizer, graph engines already in product, shadcn Dialog/Popover/Command.

---

## W. Component removal plan (after approval)

`AskGravitreEntry` or convert. Keep `/dev/ai-workspace-preview` as the **single** design harness until production absorbs an approved concept. Lucide on **visible product** nav as Nucleo lands (not a 306-file purge). Phosphor on Intelligence. `ConnectorsAtmosphere` already gone.

---

## X. Custom component plan

Relationship inspector language; run execution trace; approval queue row; connector health without app-store cards; metric strip; Nucleo role identity; workflow TRACE overlay. Build when libraries cannot express the job.

---

## Y. Implementation phases (do not start until approval)

0. Cesar **selects** concepts from the design exploration  
1. **Phase A Foundation** — primitives only (tokens, semantic Nucleo map, depth, motion, selection, focus, controls). Not every route.  
2. **Phase B AI** — selected concept on existing `AiWorkspace`  
3. **Phase C–E** Agents, Relationships, Performance  
4. Then workflows, runs, connectors (per selected discovery/management model), remaining surfaces.

---

## Z. Test strategy

Vitest for IA invariants (keep 1.0 tests). Playwright visual: 390, 430, 768, 1024, 1280, 1440, 1728; default/hover/selected/inspector/loading/empty/error. Do not claim production PASS without authenticated gravitre.app evidence.

---

## AA. Risks

Glow/token leftover fights 2.0. Misnamed connector `grid` key vs discovery strip. Marketplace PriceBadge is **authorized commerce** — do not invent. WebGL cost. Lucide file-count treated as a rewrite. Incomplete Stripe billing can still lock Command UX.

---

## AB. Dependencies

Nodus licensed source (gitignored zip; committed mirrors). Nucleo Sharp library on Cesar’s machine. Aceternity registry in `components.json` (no npm package). 21st.dev not in repo. shadcn MCP. Existing graph/React Flow. Playwright. Billing session for live proof.

---

## AC. Screenshots / prototypes

1.0 harness: `e2e/artifacts/phase-1b/*`, `phase-live-proof/*`. 2.0: this canvas. Production morph **NOT PROVEN**.

---

## AD. First production slice (recommendation)

**Gated on Cesar selecting a concept.** Then Phase A primitives (not every route) → Phase B **selected** AI workspace concept on the existing runtime. Connectors are not a “restore list” first commit.

---

## Route-by-route current state (audit)

Evidence: page reads 2026-09-17. Production feel **NOT PROVEN**.

### `/home`
Primary job: see what needs attention. Object: widgets + work. Action: open item / Ask. Structure: widget grid. Cards: justified widgets. Tabs: none. Pills: range select. Buttons: Customize + approvals. Icons: mixed Lucide/Nucleo. Hierarchy: dashboard. Motion: widget drag. Empty: per-widget honest. Loading: skeleton. Error: `WorkSectionErrorCard`. Mobile: stack risk. Generic: KPI tiles. Gravitre: Ask. Remove: nested metric cards. Retain: modular widgets.

### `/ai`
Job: talk to Gravitre. Object: conversation. Action: Ask. Structure: workspace. Cards: low. Tabs: mode query not chrome. Pills: reduced. Composer canonical. Empty: identity + suggestions. Rails: optional. Motion: layoutId. Mobile: sheet. Generic: chat template. Gravitre: one runtime. Remove: sticky task rail as default. Retain: composer, AuthGate, voice module.

### `/agents`
Job: find teammate. Object: agent. Action: open/assign. Structure: list/team/graph. Cards: surfaces. Hub: text. Identity: avatar colors. Empty: `GravitreEmpty`. Generic: SaaS directory. Retain: three views.

### `/agents/[id]`
Job: configure one agent. Text sections. Totals disclosure. Chat summons workspace. Retain: document sections.

### `/agents/[id]/chat`
Job: scoped ask. Summon fullscreen. Retain route.

### `/workflows`
Job: find/run. Table-first. Grid opt-in. Totals closed. Retain table.

### `/workflows/[id]/builder`
Job: orchestrate. Canvas. Badge-heavy. Retain canvas; reduce chips.

### `/connectors`
Job: connect. Management default is **list** (`viewMode` key still named `"grid"`). Discovery is logo strip. Detail still card-heavy. Explore A/B/C; recommend B.

### `/runs` → `/activity`; `/runs/[id]`
Job: what happened. Split list + timeline detail. Retain split; add TRACE viz.

### `/approvals`
Job: decide. Queue + PreActionCard. Retain queue; one CTA.

### `/intelligence`
Job: understand. Graph-first. Hub text. Command bar kept. Retain map.

### `/intelligence/learning`
Insight cards. Flatten toward list + inspector.

### `/intelligence/performance`
Attribution; contribution cards. Target pipeline.

### `/intelligence/memory`
TabsList leftover. Flatten.

### `/models`, `/intelligence/model-studio`, `/training`
Text nav. Expert density. Retain; polish as workspace.

### `/marketplace/assets`
Discovery tiles + PriceBadge (authorized). Distinguish install vs ops.

### `/search`
Grouped list. Retain; Nucleo types.

### `/settings`, `/settings/enterprise`, `/settings/organizations`
Document + leftover cards/pills. Settings 2.0 = rows.

### `/notifications`
List. Semantic types. Retain list.

### `/sources`
Tile catalog. Leftover card-first.

---

## Cesar amendments (binding)

1. **Design exploration gate before any production visual slice.** Spec → component assembly is the failure mode to prevent.
2. **Nucleo = semantic consistency**, not zero Lucide imports. Prioritize visible authenticated UI. Classify: product / developer-only / legacy / service logos / specialized / no user impact.
3. **Validate Nucleo Sharp 24 Outline** at 14/16/18/20/24 before locking the family. Other families only with evidence (repo currently contains Sharp 24 only).
4. **Connectors:** do not decide from historical “restore list.” Split DISCOVERY vs MANAGEMENT. Prototype A/B/C.
5. **AI workspace is the reference grammar** for the whole product, not “prettier chat.”
6. Hierarchy: CONVERSATION · COMPOSER · CONTEXTUAL WORK. Compact = header + thread + composer.
7. **Rails:** no permanently irrelevant rails. History allowed expanded/fullscreen, collapsible, hidden in compact. Inspector only with selection. Execution while relevant.
8. **Three substantially different structural concepts** per priority surface.
9. No generic sparkle/brain/wand as AI identity.
10. **One harness:** `/dev/ai-workspace-preview`. No preview-v2.
11. Keep `framer-motion`; do not churn 194 files to `motion/react`.
12. After Cesar **selects** a direction: Phase A Foundation primitives → B AI → C Agents → D Relationships → E Performance. Migrate by approved surface, not hundreds of files in one commit.
13. Production proof language stays: UNIT / Playwright / visual / responsive / reduced-motion / keyboard / **authenticated live NOT PROVEN** until evidenced. Voice/tools as PASS / MANUAL / BLOCKED.

---

# Deliverables A–Q (design exploration)

**Harness:** `/dev/ai-workspace-preview` (robots noindex, mock fixtures, **no second product runtime**). Canvas: `gravitre-ux-reset-2.canvas.tsx`.

### A. Final Reset 1.0 disposition

Architecturally source-complete (one runtime, presentation map, Ask summon, focus contract, IA flatten, disclosure, layoutId morph in harness). Visual language unfinished. Authenticated gravitre.app **NOT PROVEN**. Do not reopen runtime unless regression.

### B. Final 2.0 scope

Visual + interaction + iconography + motion + surface-model evolution. Not a component-library assembly pass. Not a Lucide purge. Not a second chat product.

### C. Nucleo (SELECTED)

Nucleo **Sharp 24 Outline**. Sizes: 14 row/table · **16 default** · 18 secondary · 20 composer/command · 24 identity/graph only. Function icons. No star-monitor / sparkle / brain / wand as Gravitre AI.

### D. Connectors (SELECTED B)

Discovery → management. No restore-list.

### E. AI (SELECTED B Command OS, amended)

Conversation → Command → Work → Inspect. Conversation persists. Work only when there is something to show. Inspector only when selected.

### F. Agents (SELECTED B Operating Team)

TEAM default. LIST / GRAPH remain.

### G. Relationships (SELECTED C Evidence graph)

### H. Performance (SELECTED C Diagnostic workspace)

### I. Workflows (SELECTED C Intent + orchestration)

### J. Runs (SELECTED C outcome default; B trace drill-down)

Did it work? Then inspect TRACE. Do not lead with waterfall.

### Q. Exact first production slice

Phase A primitives (`NUCLEO_SIZE`, Command OS inspector/work helpers) and Phase B Command OS on existing `AiWorkspace` (no empty inspector, work beside conversation when an artifact exists, mobile work/inspect sheets). No Lucide purge. No connector list-restore. Later surfaces still gated.

Proof bar for the AI slice: unit tests in this change · authenticated live **NOT PROVEN** · voice **MANUAL REQUIRED** · tools **NOT PROVEN**.

### K. Visual grammar

See `GRAVITRE_PRODUCT_VISUAL_SYSTEM_2.0.md` (amended). AI slice must ship tokens that generalize. Subtle effects: one local treatment at a time. Shadows = float/overlay/drag/selection, not “this is a card.”

### L–N. Motion / depth / responsive

See motion doc + harness (EXPAND morph, FOCUS graph, TRACE workflow/run, REVEAL inspector, RESOLVE approval). Reduced motion = immediate state. Responsive: recompose (mobile sheet / list / focused node), don’t stack cards. Viewports 390–1728 in later visual regression — **NOT PROVEN** until Playwright on an approved concept.

### O. Primitives (create only when they encode Gravitre behavior)

Candidates: Trace, Flow, Focus, Resolve, Status, EntityIdentity, AgentIdentity, ExecutionPath, ContextIndicator, Inspector, CommandSurface. Not a component trophy case.

### P. Implementation sequence (after Cesar selects concepts)

**Phase A** Foundation on **approved primitives only** (tokens, semantic Nucleo map, depth, shadow, motion, selection, focus, controls) — not every route.  
**Phase B** AI workspace (empty, conversation, compact, expanded, fullscreen, sources, execution, artifact, voice/context).  
**Phase C** Agents · **D** Relationships · **E** Performance · then workflows, runs, connectors (per selected concept), approvals, intelligence, models/training, settings, marketplace.

### Q. Exact first production slice

Phase A primitives and Phase B Command OS on existing `AiWorkspace`. Phase C Operating Team on `/agents`. Phase D Evidence graph on Learning relationships. Phase E Diagnostic workspace on Performance. Phase F Intent + TRACE on the workflow builder started 2026-09-18. No Lucide purge. No connector list-restore.

Proof bar for that slice: unit tests in this change · Playwright / visual regression / authenticated live **NOT PROVEN** · voice **MANUAL REQUIRED** · tools **NOT PROVEN**.

---

## Final visual review packet

Harness: `/dev/ai-workspace-preview?s=&scene=`  
Artifacts: `e2e/artifacts/ux-reset-2-review/`

## STOP

Phase I Approvals queue + one primary CTA started. Remaining hubs (intelligence, models/training, settings, marketplace) remain later.

# Gravitre 3.0 Extrovert Design — completion ledger

Started: 2026-10-03  
Base: `origin/main` `2b39b87b` (PR #297 Emerald Intelligence migration, merged)  
Active branch: `feat/gravitre-3.0-extrovert-design`  
Reason for new branch: `feat/emerald-intelligence-completion` / PR #297 is merged. This is the single continuation branch for Extrovert completion + Figma Brand Foundation alignment.

Figma file:  
https://www.figma.com/design/OsDKeRy9HwfSKR3e9YyOFM/Gravitre-%E2%80%94-Brand-Foundation---Creative-Direction?node-id=6-2

## Historical Figma capability check (see resolved access and provenance below)

Live tool catalog was inspected. Namespace `project-0-Gravitre Operator AI-Figma` is present with `get_metadata`, `get_design_context`, `get_variable_defs`, and related tools.

| Value class | Used? | Notes |
| --- | --- | --- |
| Exported Figma variables | NO | `get_variable_defs` on `0:1` hit Starter-plan MCP rate limit; `6:2` required a selected layer |
| Inspected fills / page XML labels | YES | Page `0:1` “01 — Brand Foundation”; Color Foundation labels on node `1:3` (Organized Intelligence 1440×1996): Porcelain `#F7F8F6`, Ink `#151A1D`, Graphite `#485257`, Mist `#E6ECEA`, Signal `#20B9A5`, Ion `#2D8CFF`, Warmth `#F26B45`. Marketplace study on same page lists Run IT / Grow Revenue / Market Smarter / Serve Customers. These are inspected labels, not exported variables. |
| Written contract + first `:root` | YES | Documented Brand Foundation tokens preserved. Inspected Signal `#20B9A5` / Ion `#2D8CFF` were **not** applied as a rematch. |
| Page 02 / 03 implementation frames | UNAVAILABLE | Current file metadata listed only page `0:1`. Exact Figma matching for Marketplace `8:2`, Intelligence `10:5`, Agents, Operate, Builder, Analytics, Handoff, Motion remains **unverified**. |

Historical note: an earlier session recorded Figma as absent from the catalog. That limitation is superseded by this check. Browser-only views of page 03 from earlier sessions stay historical, not current MCP evidence.

## Brand Foundation tokens (applied)

Source: written contract + first `:root` in `globals.css` (PR #297). Hexes match that contract. Later Carbon `:root` had been overwriting them with `#2fbf8f` / Ion violet. No exported-variable correction this stream.

| Token | Hex | Role |
| --- | --- | --- |
| `--g-emerald` / `--g-brand` / `--brand` / `--signal-500` | `#00A878` | Brand / action |
| `--g-emerald-deep` / `--g-brand-active` / `--signal-600` | `#007F5F` | Deep emerald |
| `--g-brand-hover` | `#008F67` | Hover (existing named step) |
| `--g-emerald-mint` / `--g-brand-soft` | `#CFF7E8` | Signal mint |
| `--g-emerald-pale` / `--signal-wash` | `#EAF8F2` | Pale emerald |
| `--g-brand-muted` / `--signal-300` | `#63D6B3` | Muted emerald |
| `--g-carbon` | `#101816` | Carbon / ink |
| `--g-bone` | `#F5F3EC` | Bone canvas |
| `--g-electric` / `--ion-500` | `#315CFF` | Functional blue (Ion violet retired) |
| `--ion-300` | `color-mix` of `#315CFF` toward white (`#6B8AFF`) | Lighter electric — implementation step |
| `--g-warmth` | `#FF654D` | Coral / attention |

`--primary` stays ink (`--ink-950`) for shadcn actions. Emerald is brand/action via `--g-brand` / `--g-emerald`, not an automatic healthy label.

`--g-intelligence` / `--g-intelligence-bright` rematched from analytical violet (`#5647c9`) to Electric (`#315CFF` / `#6B8AFF` dark / `var(--ion-500)`). Identity palette `--color-violet-700` / `--color-purple-700` `#5647c9` left for agent/department identity.

`GlowOrb` remains unused on product routes. Decorative `GridPattern` removed from `/welcome` and `/multi-agent-run`. Functional `PulseRing` / `StatusBeacon` / `DataStream` / `AnimatedCounter` preserved.

## Historical gate snapshot (superseded by dated implementation records below)

| Field | Value |
| --- | --- |
| ACTIVE_BRANCH | `feat/gravitre-3.0-extrovert-design` |
| COMPLETION_PR | [draft #298](https://github.com/cesarbohjr/gravitre-saas-backend/pull/298) |
| CANDIDATE_SHA | `224d79a3` |
| REVIEWED_SHA | `db2eea5e` (review findings applied on this working tree) |
| IMPLEMENTATION_COMPLETE | NO — page 03 Figma frames unavailable; owner-live blocked; overlay stacking on mobile pack bar still open |
| AUTOMATED_CHECKS | LOCAL PASS — `pnpm test` 1,127; lint 0 errors; `tsc --noEmit` 0; `pnpm build` 0; brand/surface/cognitive guards PASS. GitHub CI on the new SHA not yet attached |
| BILLING_E2E | NOT_APPLICABLE for required PR CI — job only runs on `workflow_dispatch` (`ci.yml` `billing-e2e`). This PR’s billing pages received composition/token supporting work only; no checkout, plan, or entitlement behavior change. Not marked passed. |
| OWNER_LIVE_ACCEPTANCE | NOT_RUN / BLOCKED — owner login wall |
| MERGE_READY | NO |
| MAIN_SHA | `8c737d50` (includes PR #299 MSP blog restoration) |
| DEPLOYED_SHA | production marketing on `gravitre.app` serves PR #299 MSP route (HTTP evidence below) |
| PRODUCTION_VERIFIED | PARTIAL — MSP blog route + hero asset verified on canonical production URL; completion PR preview re-check pending post-push |
| CAUGHT_UP | NO |
| OUTCOME_VERIFIED | not claimed |

## Unrelated published content preservation audit (2026-10-03)

Scope: before merging PR #298, confirm Emerald migration (PR #297) and the Extrovert completion branch did not drop unrelated marketing/blog routes, images, or registrations. A green build does not prove routes survived.

### PR #299 verification (repository history)

| Check | Result | Evidence |
| --- | --- | --- |
| PR #299 merged to `main` | PASS | merge commit `8c737d50` @ 2026-10-03T16:38:38Z — “Restore MSP blog post dropped by Emerald Intelligence migration” |
| Restored content module | PASS | `apps/web/app/(marketing)/blog/content/governed-ai-for-msps.tsx` added (+161 lines) |
| Restored `posts.tsx` wiring | PASS | import `governedAiForMspsPost` + array entry in same merge |
| Restored hero asset | PASS | `apps/web/public/images/blog/governed-ai-for-msps-hero.jpg` (+226113 bytes) |

Root cause (from merge message): PR #297 landed from a snapshot of `main` that predated MSP post merges (#294/#295); the post was missing on `2b39b87b`, not deleted file-by-file inside the Emerald diff against `2c23a56b` (marketing tree unchanged in that merge).

### PR #298 catch-up vs `main`

| Check | Result | Evidence |
| --- | --- | --- |
| Branch contained MSP post before catch-up | FAIL | `origin/feat/gravitre-3.0-extrovert-design` @ `2953b1eb` lacked `governed-ai-for-msps.tsx`, hero JPG, and `posts.tsx` registration |
| `merge origin/main` on completion branch | PASS | merge commit on this branch re-applied PR #299 three-file restoration without conflict |
| Extrovert marketing diffs vs `main` (intentional) | PASS | only `enterprise-ai-governance.tsx` hero gradient token swap, `guides/page.tsx` + `layout.tsx` token/class tweaks — no other blog slugs or images removed |
| PR #298 file deletions vs `main` | PASS | `git diff origin/main...HEAD --name-status` shows **zero** `D` entries (adds/modifies only) |

### Broader accidental-removal scan (`2c23a56b` → `origin/main`)

Marketing/content delta on `main` since pre-Emerald parent: **only** PR #299 MSP restoration (3 files). No other blog posts, hero images, or marketing routes removed on `main` in that range.

Remote branch `blog/governed-ai-agents-smb-msp-revops` still carries the same published slug set as `main`; no additional published posts to restore without product authorization.

### Repairs on this branch

| Item | Action |
| --- | --- |
| MSP post + hero + registration | Restored via `merge origin/main` (PR #299), not manual cherry-pick |
| Regression coverage | Added `apps/web/__tests__/marketing/blog-content-registry.test.ts` — slug in `getAllBlogSlugs`, listing, hero path, on-disk asset |

### Production URL verification (canonical, no cache-bust query)

| URL | HTTP | Cache / routing notes |
| --- | --- | --- |
| `https://gravitre.app/blog/governed-ai-for-msps` | **200** | `x-matched-path: /blog/[slug]`, `x-pathname: /blog/governed-ai-for-msps`, `x-vercel-cache: MISS`, `age: 0` @ 2026-10-03T16:45:59Z |
| `https://gravitre.app/images/blog/governed-ai-for-msps-hero.jpg` | **200** | `content-type: image/jpeg`, `age: 0` @ 2026-10-03T16:46:00Z |

No cached 404 observed on canonical production URLs at verification time. If 404s reappear after deploy, inspect `x-vercel-cache`, `age`, and `x-matched-path` before attributing to CDN alone.

### Preview verification (PR #298 @ `224d79a3`)

| Check | Status | Notes |
| --- | --- | --- |
| Vercel preview anonymous HTTP | BLOCKED | `gravitre-saas-backend-git-feat-gravitre-30-e-b3cc3e-gravitre-ai.vercel.app` → 302 Vercel SSO (not a CDN 404) |
| Local dev @ `224d79a3` (`localhost:3055`) | PASS | `GET /blog/governed-ai-for-msps` **200**, `x-pathname` set; body contains title + `governed-ai-for-msps-hero`; `/blog` index links slug |

## Marketplace reconciliation matrix

Sources: `backend/app/marketplace/seed_catalog.py`, `department_pipelines/catalog.py`, `intelligence_packs/catalog.py`, `docs/delivery/phase0-twelve-pack-marketplace-vision.md`, `LEGACY_PACK_SLUG_MAP`, PR #297 (removed marketplace3 certification/portfolio modules and capability_package skill-tree surfaces from `main`). No packs invented. No removed modules restored.

`original requirement | current asset/pack | catalog source | change history | content status | UX/UI status | missing capability | next action`

### Department packs (installable catalog type `department_pack`)

| original requirement | current asset/pack | catalog source | change history | content status | UX/UI status | missing capability | next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Marketing ops / `marketing-ops` | `marketing-operations-pack` | `seed_catalog._department_packs` | Legacy slug mapped | Seeded agents/workflow/RAG/connectors | Shared Discover catalog + detail + grouped contents + pipeline alias `Marketing`→`marketing` + mobile install/uninstall | Paid pack; required GA/Apollo not connected in fixture | Fixture visual of this slug; owner-live install IDs |
| MSP / ops | `msp-operations-pack` | seed | Current slug | Seeded coordinator/runbooks/weekly status | Shared chrome; pipeline alias `Operations`→`msp` | — | Fixture visual; owner-live |
| RevOps / `sales-ops` | `revenue-operations-pack` | seed | Legacy `sales-ops` mapped here | Seeded RevOps + sales pipeline + exec rollup | Shared chrome; pipeline alias `Revenue Operations`→`sales`; installed fixture | — | Fixture visual of installed state; owner-live runtime IDs |
| Customer Success | `customer-success-pack` | seed | Current slug | Seeded CS agent/health rubric/monitoring | Shared chrome; **no department pipeline** (honest) | No pipeline by design | Do not invent a CS pipeline; fixture visual of pack-only detail |
| HR ops | `hr-operations-pack` | seed | Current slug | Seeded HR coordinator/policy RAG/onboarding | Shared chrome; pipeline `HR`→`hr` | Live HRIS/ATS governance-gated | Fixture visual; owner-live |
| Support / `support-ops` | `support-operations-pack` | seed | Legacy slug mapped | Seeded triage/Zendesk/SLA | Shared chrome; **no department pipeline** (honest) | Paid pack; Zendesk required | Fixture visual of blocked install; owner-live |
| Finance department pack / `finance-ops` | **none** | pipeline `default_department_pack_slug=None`; legacy `finance-ops` maps to `revenue-operations-pack` | Consolidated, not a Finance pack | N/A | Finance pipeline exists without a default department pack | Honest gap | Do not invent a Finance department pack |
| Compliance department pack | **none** | never seeded | 12-pack vision listed Compliance as NEW | N/A | N/A | Never built | Do not invent |

### Intelligence packs (separate catalog type; 12-pack vision)

| original requirement | current asset/pack | catalog source | change history | content status | UX/UI status | missing capability | next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Marketing Intelligence | `marketing-intelligence-pack` | `intelligence_packs/catalog.py` | Exists | Assignments + GSC/GA4/HubSpot/Canva refs | Same Marketplace detail chrome when listed | Raw query Memory/KG gated | Catalog-vs-runtime ID proof on owner org |
| RevOps Intelligence | `revops-intelligence-pack` | same | Exists | HubSpot pipeline snapshot | Shared chrome | CRM-only; finance F3 separate | Owner-live |
| Sales Intelligence | `sales-intelligence-pack` | same | Exists (vision “shipped”) | Pipeline/CRM | Shared chrome | — | Owner-live |
| Prospecting | `prospecting-intelligence-pack` | same | Exists; not merged into Sales | Apollo/PDL/Crunchbase/ZoomInfo BYO | Shared chrome | Contact Memory/KG STA-312 | Owner-live |
| AI Search | `ai-search-intelligence-pack` | same | Exists | Visibility analyst + GSC | Shared chrome | No scrape | Owner-live |
| Finance Intelligence | `finance-intelligence-pack` | same | Exists; live connectors gated | Cash-flow analyst refs | Shared chrome | Governance before live QB/Xero/NetSuite/Plaid | Do not activate connectors |
| HR Talent Intelligence | `hr-talent-intelligence-pack` | same | Exists; live HRIS gated | Recruiting analyst refs | Shared chrome | Governance before live Workday/Greenhouse | Do not activate connectors |
| Support Intelligence | `support-intelligence-pack` | same | Extra vs original 12 | Support analyst | Shared chrome | — | Owner-live |
| Customer Success Intelligence | `customer-success-intelligence-pack` | same | Exists | Health analyst | Shared chrome | Shared Pack KPI dashboard still NEW from Phase 0 | Owner-live |
| MSP Intelligence | `msp-intelligence-pack` | same | Exists | Vuln/CISA/NVD | Shared chrome | — | Owner-live |
| Executive | `executive-intelligence-pack` | same | Exists | Executive analyst | Shared chrome | — | Owner-live |
| Business OS / platform | `platform-health-intelligence-pack` | same | Renamed/extended from Business OS | Platform reliability | Shared chrome | — | Owner-live |
| Compliance Intelligence | **none** | Phase 0: NEW / guidance-docs only | Never catalogued | N/A | N/A | Never built | Do not invent |

PR #297 removal claims: marketplace3 certification/portfolio modules and capability_package skill-tree product surfaces were removed on `main` (verified as the merged base of this branch, not restored). Treat older “six remaining packs complete” chat claims as historical.

Pipeline-linked defaults are four (`revenue-operations-pack`, `marketing-operations-pack`, `hr-operations-pack`, `msp-operations-pack`). That is not the complete Marketplace catalog.

## Route inventory

`route | family | nested | current gap | files | verification | evidence | SHA | status | blocker`

| route | family | nested | current gap | files | verification | evidence | SHA | status | blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/home` | Understand | KPI, time, drill-down | Already composed Understand; owner metrics not live-checked | `components/home/home-dashboard.tsx` | populated fixture + owner metrics | fixture pending this SHA; owner-live | `db2eea5e`+ | IMPLEMENTED ON BRANCH | OWNER_LIVE |
| `/ai` | Create | composer, history, tools | Embedded exit + WM persist wired; stream/voice/approvals unchanged | `app/ai/_components/ai-workspace.tsx` | stream + persist + window modes | fixture `/e2e/shots/ai` exists; owner-live | this pass | IMPLEMENTED ON BRANCH | OWNER_LIVE + fixture visual this SHA |
| `/agents` | Manage | list, inspector | Glow fallbacks removed earlier | `app/agents/page.tsx` | list/inspector | fixture `/e2e/shots/agents` exists; owner-live | prior | IMPLEMENTED ON BRANCH | OWNER_LIVE + fixture visual this SHA |
| `/agents/[id]` | Manage | tabs, autonomy | Stored avatar IDs untouched | `app/agents/[id]/page.tsx` | save persist | fixture `/e2e/shots/agent-detail` | prior | IMPLEMENTED ON BRANCH | OWNER_LIVE |
| `/connectors` | Manage | catalog, instance | Connection status must stay real | `app/connectors/page.tsx` | reconnect | fixture `/e2e/shots/connectors` | prior | IMPLEMENTED ON BRANCH | OWNER_LIVE |
| `/sources` | Manage | ingest, detail | Readiness honesty | `app/sources/page.tsx` | inventory | owner-live | prior | PRIOR / UNVERIFIED | OWNER_LIVE |
| `/workflows` | Operate | list | Composition operate | `app/workflows/page.tsx` | safe run | fixture `/e2e/shots/workflows` | prior | IMPLEMENTED ON BRANCH | OWNER_LIVE |
| `/workflows/[id]/builder` | Create | canvas, inspector | Functional run glow left | `app/workflows/[id]/builder/page.tsx` | persist + run | fixture `/e2e/shots/builder` | prior | IMPLEMENTED ON BRANCH | page 03 frame unavailable |
| `/intelligence` | Understand | map, rails | Indigo stubs removed; idle no pulse | `app/intelligence/page.tsx` | filters + evidence | fixture `/e2e/shots/intelligence-field` | prior | IMPLEMENTED ON BRANCH | OWNER_LIVE + page 03 unverified |
| `/marketplace/assets` | Discover | types, install | Mobile search-first + pack tiles | `app/marketplace/assets/page.tsx` | catalog + filters | new `/e2e/shots/marketplace` | this tree | IMPLEMENTED ON BRANCH | fixture visual + OWNER_LIVE |
| `/marketplace/assets/[slug]` | Discover | detail, readiness, mobile actions | Uninstall restored in overflow; bar above MobileBottomNav | `app/marketplace/assets/[slug]/page.tsx` | install/uninstall states | new `/e2e/shots/marketplace-pack/[slug]` | this tree | IMPLEMENTED ON BRANCH | fixture visual + OWNER_LIVE |
| `/marketplace/installed` | Operate | inspector, uninstall | Installed management | `app/marketplace/installed/page.tsx` | uninstall + deep links | new `/e2e/shots/marketplace-installed` | this tree | IMPLEMENTED ON BRANCH | fixture visual + OWNER_LIVE |
| `/approvals` | Operate | queue | Actor/context | `app/approvals/page.tsx` | approve/reject | fixture `/e2e/shots/approvals` | prior | IMPLEMENTED ON BRANCH | OWNER_LIVE |
| `/activity` | Operate | runs | Execution state | `app/activity/page.tsx` | run vs activity | fixture `/e2e/shots/activity` | prior | IMPLEMENTED ON BRANCH | OWNER_LIVE |
| `/audit` | Configure | events | Real org events | `app/audit/page.tsx` | filters | owner-live | prior | PRIOR / UNVERIFIED | OWNER_LIVE |
| `/notifications` | Operate | list | — | `app/notifications/page.tsx` | mark-read | owner-live | prior | PRIOR / UNVERIFIED | OWNER_LIVE |
| `/settings/**` | Configure | billing, team, profile | Extracted row chrome; IA test retargeted to real SSO/notifications/memory policy | `app/settings/**` + `components/settings/*` | save + entitlements | billing e2e not required on PR CI | this pass | IMPLEMENTED ON BRANCH | OWNER_LIVE; logo upload unavailable |
| `/plays` | Operate | play, results | Row queue, empty state, honest missing approvals | `app/plays/**` | real play data | owner-live | this pass | IMPLEMENTED ON BRANCH | OWNER_LIVE + fixture visual |
| `/admin/intelligence` | Understand | admin tabs | Glow remnants already empty; Understand composition present | `app/admin/intelligence/**` | admin-only | owner-live | this tree | IMPLEMENTED ON BRANCH | role gate + OWNER_LIVE |
| `/training` | Create | onboarding training | Error card, loading/empty split, freshness on successful fetch, mobile nav clearance | `app/training/page.tsx` | — | owner-live | this pass | IMPLEMENTED ON BRANCH | OWNER_LIVE |
| `/schedules` | Operate | calendar, list | Org page already operate; workflow schedules now tagged operate | `app/schedules/**`, `app/workflows/[id]/schedules/page.tsx` | cron persist | owner-live | this pass | IMPLEMENTED ON BRANCH | OWNER_LIVE; detail sheet still unused |
| `/metrics` | Understand | charts, export | Omitted overview/throughput stay unreported; error/retry on overview | `app/metrics/page.tsx` | charts | fixture `/e2e/shots/metrics` | this pass | IMPLEMENTED ON BRANCH | OWNER_LIVE; visual overlay on stale local shot |
| `/environments` | Manage | topology | Health, resource counts, API URL, timestamps no longer invented | `app/environments/page.tsx` | real env fields | owner-live | this pass | IMPLEMENTED ON BRANCH | OWNER_LIVE |
| `/welcome` | Create | role pick | Decorative GridPattern removed | `app/welcome/page.tsx` | first-run | fixture not added | this tree | IMPLEMENTED ON BRANCH | — |
| marketing `/*` | Discover | legacy features | Decorative purple rematched to Electric | `components/marketing/features/legacy-page.tsx` | visual | historical `77ca50ce` marketing shots | this tree | IMPLEMENTED ON BRANCH | re-shot this SHA |
| `/multi-agent-run` | Manage | swarm | Decorative GridPattern + violet orb removed | `app/multi-agent-run/page.tsx` | execution states | owner-live | this tree | IMPLEMENTED ON BRANCH | OWNER_LIVE |

Hidden / legacy (reachable, do not invent new paths): `/operator`, `/command-center`, `/chat`, `/assistant`, `/tasks`, `/systems`, `/admin/intelligence`, `/training`, `/multi-agent-run`, `/metrics`, `/outcomes` → activity.

## Inspection vs unverified vs login-blocked

| Surface | Actually inspected | Visually unverified | Owner tasks blocked by login |
| --- | --- | --- | --- |
| Marketplace catalog | Code + fixtures added + unsigned historical frame `8:2` | Fixture render this SHA; live catalog | Browse live catalog; install; runtime IDs |
| Marketplace pack detail (6 slugs) | Code; mobile uninstall overflow; pipeline alias | Fixture render each slug this SHA | Open each real pack |
| Marketplace installed | Code + fixture payload | Fixture render this SHA | Owner-org installs |
| Agents list/detail | Code + existing shot routes | Fixture re-render this SHA | List + save |
| Intelligence | Code + existing shot routes | Fixture re-render this SHA | Values / filters / evidence |
| Operate / Builder / Approvals | Code + existing shot routes | Fixture re-render this SHA | Persist + approved safe run |
| Analytics / metrics | Code (Understand; ChartTooltip) | Fixture `/metrics` not added | Live metrics |
| Handoff / Motion | Decorative install glow/Sparkles removed earlier | Page 03 frames not in Figma file | Owner walk of Lock→Route→Handoff→Resolve where real |

## Owner-live checklist (NOT_RUN)

Every row: `NOT_RUN` until authenticated owner-org proof on a recorded SHA.

- Dashboard metrics / time / drill-down
- Agents list + detail save + history
- Connectors real status + approved reconnect
- Sources inventory + ingestion
- Workflows builder persist + approved safe run
- Intelligence values / filters / evidence
- AI workspace retrieve / stream / tools
- Marketplace each catalog pack surface + install IDs
- Billing: separate workstream (`workflow_dispatch` only)

## Historical fixture visual evidence (SHA `77ca50ce` — do not relabel as current)

Preview: `https://gravitre-saas-backend-isq7czh5j-gravitre-ai.vercel.app` (Vercel READY at that SHA).

| Check | Result | Class |
| --- | --- | --- |
| Marketing `/` desktop | Rendered on preview; Brand Foundation emerald heading, no page-theme purple | fixture @ `77ca50ce` |
| Marketing `/features` desktop | Coordinate → Act → Approve → Resolve present; no invented prices | fixture @ `77ca50ce` |
| Marketing `/features` 390×844 | Stacked header, wrapping chips, cookie sheet; layout holds | fixture-responsive @ `77ca50ce` |
| Product `/marketplace/assets`, `/agents` | Preview redirects to `https://gravitre.app/login` | login-blocked |
| `/e2e/shots/agents` on preview | 404 (shot routes gated out of production builds) | fixture unavailable on preview |
| Local typecheck | `npm run typecheck` in `apps/web` exit 0 | automated-local @ `77ca50ce` |
| Isolated Conversation Smoke | Not used | n/a |

## Current automated evidence (candidate `4b851ea6`)

| Check | Result | Class |
| --- | --- | --- |
| `__tests__/gravitre/micro-label-guard.test.ts` | 4 passed; guard not weakened | automated-local |
| `__tests__/gravitre/marketplace-mobile-actions.test.ts` | 2 passed — uninstall on mobile bar; bar above nav | automated-local (source) |
| `__tests__/gravitre/marketplace-department-pipeline.test.ts` | 2 passed | automated-local |
| `pnpm test` | 1,127 passed / 183 files on the pre-fixture tree; focused 8/8 after fixture/pipeline tests | automated-local |
| lint | 0 errors / 276 pre-existing warnings | automated-local |
| typecheck | `tsc --noEmit` exit 0 | automated-local |
| build | `pnpm build` exit 0 | automated-local |
| brand / chat-surface / status-leak / intelligence-surface / cognitive | PASS | automated-local |
| Web CI @ `db2eea5e` | FAIL `micro-label-guard` — fixed on this tree, not yet on a new SHA | CI historical |
| Billing E2E | `workflow_dispatch` only in `ci.yml`; no billing behavior change this PR | NOT_APPLICABLE on PR CI |

## Current fixture visual evidence (localhost:3055, Northwind shots — not owner-live)

Use `http://localhost:…` not `127.0.0.1` (HMR/dev origin). Shot token short-circuit in `getAccessToken` is gated on `__GRAVITRE_AI_INSTRUMENT` (shots layout only; 404 in production).

| Surface | Viewport | Rendered states | Result | Class |
| --- | --- | --- | --- | --- |
| `/e2e/shots/marketplace` | desktop | Populated 6 department packs; Discover chrome; grouped contents sentence-case; paid Marketing/Support use existing seed prices; RevOps in Installed | Visually verified | fixture |
| `/e2e/shots/marketplace-pack/revenue-operations-pack` | desktop | Installed, grouped contents, Sales Pipeline via department alias, Uninstall + Open installed | Visually verified | fixture |
| same slug | 390×844 | Sticky bar above MobileBottomNav; Open installed + Clone + More; Uninstall in overflow | Visually verified; floating issues badge overlaps the bar | fixture-responsive |
| `/e2e/shots/marketplace-pack/marketing-operations-pack` | desktop | Uninstalled paid; GA/Apollo blockers; Buy & install; grouped contents | Visually verified | fixture |
| `/e2e/shots/marketplace-installed` | desktop | 1 active install (RevOps); inspector closed until select | Visually verified | fixture |
| `/e2e/shots/agents` | desktop | Populated roster/team; Deal Desk executing; filters | Visually verified | fixture |
| `/e2e/shots/intelligence-field` | desktop | Field + Knows/Learns/Predicts tabs; graph nodes; honest empty attention/learning; evidence rail | Visually verified | fixture |
| `/e2e/shots/workflows` | — | Navigation started; screenshot not captured this pass | PARTIAL | fixture |
| Owner product `/marketplace` `/agents` | preview | Login redirect | login-blocked | owner-live NOT_RUN |

## Next concrete actions

1. Finish lint, typecheck, build, and brand/surface guards on this tree.
2. Render `/e2e/shots/marketplace`, each pack slug, installed, agents, intelligence, workflows, builder, approvals at desktop and 390px. Record SHA after commit.
3. Owner sign-in required for owner-tenant acceptance. Isolated Conversation Smoke is not owner proof.
4. Exact Figma page 03 matching stays unverified until those frames exist in the live file and exported variables are available.
5. MERGE_READY stays NO until required Web CI is green on the final SHA and fixture visual evidence for changed product routes is attached. Production deploy is not a pre-merge requirement.
6. CAUGHT_UP stays NO until in-scope design work is merged, deployed, and production-verified.

## Direct implementation pass — 2026-10-03

Starting branch head: `4390f7ba027aa4572acad4d013a09429d2722eb9`. This section records new work; earlier gate snapshots and screenshot rows remain historical and are not evidence for this patch.

Implemented:

- Move the floating AI launcher above the mobile Marketplace pack action bar only while that bar is mounted. Preserve its normal mobile position elsewhere and desktop docking.
- Increase pack-detail bottom clearance for the stacked navigation, action bar and AI launcher. This does not resolve the separate reported development issues-badge overlap; that needs a rendered inspection.
- Restrict screenshot-token substitution to instrumented `/e2e/shots` paths in non-production or explicitly enabled public E2E builds. Ordinary product routes and normal production builds retain real user/session validation, even if the browser instrumentation flag is set.
- Add eight behavioral auth-isolation tests and a launcher clearance regression assertion.

Verification of the changed working tree:

| Check | Result | Limit |
| --- | --- | --- |
| Full Vitest suite | 1,141 passed / 186 files | Automated local, not owner-live |
| Focused auth/mobile tests | 20 passed / 3 files | Offset assertions do not prove rendered geometry |
| TypeScript `tsc --noEmit` | PASS | Not a production build |
| ESLint on changed code/tests | 0 errors; 1 existing auth navigation warning | Not full-repository lint |
| Tailwind 4.2 compile of conditional mobile offset | PASS; emitted matching `:has` selector and bottom calculation | No screenshot comparison |
| `git diff --check` | PASS | Whitespace only |
| Figma variable export on `0:1` | BLOCKED: Starter-plan MCP call limit | No tokens extracted; no palette changes made |
| Browser / owner-live acceptance | NOT_RUN for this patch | No visual or owner acceptance claimed |

MERGE_READY = NO. CAUGHT_UP = NO. Continue the full route/pack design work after obtaining an accessible authoritative Figma source; this bounded fix is not completion of the design sprint.

## Continued Figma implementation — 2026-10-03

Base: `35ea020793bb392f7fbcb99e5833ee0cb2d02fdb`. Historical evidence above does not validate this patch. The earlier MCP plan-limit blocker is resolved: page 03 frames are now accessible. The file exposes no local variable collections or styles; exact layer fills and typography were extracted, as documented in `gravitre-figma-token-provenance.md`. Do not describe this as a variable export.

| Surface / Figma frame | Changes implemented on existing routes | Remaining acceptance |
| --- | --- | --- |
| Agents `10:52` | Emerald identity overview and capability panel for the actual filtered roster; saved icon/color/ID preserved; model, workflow count and explicit connected systems; working inspect/configuration actions | Authenticated roster, save/history, desktop/mobile comparison |
| Intelligence `10:5` | Space Grotesk heading, actual snapshot summary, carbon graph canvas and light evidence rails; filters, lenses, relationships, map controls and analytical data retained | Authenticated map interaction, evidence/filter correctness and responsive geometry |
| Operate / Activity `10:101` | Current-view counts for running, approval, completed and verified; successful execution is not verification; filter scope disclosed | Queue/decision persistence and owner evidence |
| Builder `10:159`, responsive `20:2` | Carbon inspector, tablet cutover at 1024px, configuration/Meson/trace sheets, phone-width configuration sheet; real canvas, persistence and run actions retained | Desktop/tablet/mobile render; persist and approved safe run |
| Analytics `14:2` | Flat KPI surfaces, display typography, semantic Figma chart palette, readable carbon tooltips, unique sparkline gradient IDs; dynamic charts and series retained | Live values, legends/tooltips, chart density and mobile disclosure |
| Shared / marketing | Display-font product headings, stable live dots, decorative screenshot-wrapper glow removed | Rendered regression across affected routes |

New regression coverage checks saved agent inspection IDs, absence of inferred connected systems, tablet/phone breakpoint changes and subscription cleanup, filtered activity counts and verification truth. Figma specimen numbers, names, charts and statuses were not substituted for live data.

The full plan remains incomplete. Prior Marketplace changes are published at the base SHA; nested real-pack install/readiness/failure acceptance remains pending. No new prices, claims, badges, catalog entries or Enable toggles were added. The MSP article restoration is outside this patch and must remain intact.

Visual / OWNER_LIVE = NOT_RUN for this patch. The local browser service blocks localhost; the external preview requires sign-in. Historical fixture screenshots are not evidence for the newly changed layouts. IMPLEMENTATION_COMPLETE = NO; MERGE_READY = NO; CAUGHT_UP = NO. Required GitHub CI must be checked on the published candidate SHA.

Local verification: full Vitest 1,147 passed in 189 files; TypeScript passed; full ESLint 0 errors / 275 warnings; production Next.js build passed (including the tablet trace sheet); chat-surface, status-leak, intelligence-surface and brand guards passed. Cognitive regression guard passed with Python import smoke and targeted pytest skipped by that script. `git diff --check` passed. The first pnpm invocation aborted before running checks because it attempted dependency installation; the reported checks were subsequently run successfully with npm against the installed dependencies.

Published layout patch: `9d0aa58fd7f03fa06d016ac0a66a14cef34fed74`, tree `ebda9efd96e3b73031c7ad1a82a2ef8e95d87420`, identical to the locally tested tree. CI and Marketing Lighthouse were still running when checked. Follow-up cascade audit corrects light muted text to #65716B and white panel surfaces to #FFFFFF; dark contrast overrides are preserved. Builder configuration sheets also override the shared Sheet component's `sm:max-w-sm` so the specified 540px desktop/tablet width actually takes effect. Focused regression checks passed 9/9; brand and whitespace guards passed. These changes do not supply missing visual/owner acceptance.

## Nested Marketplace implementation — 2026-10-03

Base `e6b500ccfa2d04c3f864a721430f24f95aa0de0c`. Its CI run `37156328214` and Marketing Lighthouse run `37156328209` were independently checked as completed/success. Those results do not apply to this next candidate. Billing E2E remains skipped, not passed.

Figma Marketplace `8:2`, responsive studies `20:2` and handoff `22:2` were read with design context and screenshots. This pass extends their hierarchy and disclosure rules to existing nested surfaces; Figma does not provide a separate pixel reference for each pack detail or install state. No specimen charts, counts, packs, prices, or runtime claims are substituted for application data.

| Surface | Actual changes | Outstanding verification |
| --- | --- | --- |
| `/marketplace/assets/[slug]` | Emerald outcome-first overview, actual catalog/entitlement context, display typography, desktop actions adjacent to overview; phone bar has one primary action plus Clone/Uninstall overflow; 44px primary/menu targets; existing safe-area/launcher clearance retained | Rendered 1440/834/390 geometry and all six real department packs on owner tenant |
| Pack preview sheet | Actual outcome and grouped child links; shared connector checklist; readiness uses `canInstall` plus purchase requirement, not just connected apps | Real entitlement/blocker transitions |
| Install sheet | Labelled steps/loading; readiness error/retry; no confirm when check fails or viewer is not admin; inline install failure; success requires server `installed`; fresh check entitlement; included-child disclosure; resets session on asset change/external close | Paid checkout, readiness recovery, install/failure on owner tenant; provisioned runtime IDs |
| `/marketplace/installed` | Tablet/phone inspector sheet opened by selection; all runtime links retained instead of truncating after four; selected pack contents loaded from detail API; admin-only uninstall; fetch errors do not masquerade as empty/zero-current lists | Live installed data, uninstall/persistence, sheet focus/geometry |
| Shared contents/checklist | Required/optional child flags, wrapping titles, focused native disclosure, app-specific Connect names, connected required apps no longer presented as destructive | Responsive and keyboard visual QA across catalog/detail/install/installed |

Behavioral tests: 12 new tests cover outcome content, child routes/requirements, purchase readiness, failed checks/retry, non-admin confirm, fresh entitlement, unconfirmed install response, install failure, session reset, tablet inspector selection, complete runtime links and admin controls/error states. These use mocked data and DOM rendering; they are not browser screenshots or owner evidence.

Local checks: full Vitest 1,159 passed / 191 files; TypeScript passed; production Next.js build passed on the final code; full ESLint 0 errors / 275 warnings, changed-file ESLint clean on final code; brand/chat/status/intelligence guards passed; cognitive guard passed with Python import smoke and targeted pytest skipped by that script; whitespace check passed.

Browser access rechecked against the current branch preview: redirected to **Vercel login** before the product route loaded. Local browser access was previously rejected by the browser service. No new rendered layout or owner acceptance is claimed. Prior screenshots and base-SHA CI are historical. IMPLEMENTATION_COMPLETE = NO; OWNER_LIVE_ACCEPTANCE = NOT_RUN; MERGE_READY = NO; CAUGHT_UP = NO. The PR remains draft and unmerged.

## Connection, source and approval disclosure — 2026-10-04 UTC

Base: `46b33a297b2d498ea1a508304448188bd34a82c2`. GitHub CI `37158380523` and Marketing Lighthouse `37158380533` were independently checked as completed/success. These base results do not establish candidate CI.

Figma handoff `22:2` was read through design context with its screenshot. It specifies Manage identity/capability, tablet sheets, phone task/disclosure, status text, and preservation of charts and operational behavior. There is no separate Sources or Connectors pixel specimen in this inspection. This pass applies the handoff contract to existing routes; it does not claim an exact screen match.

| Surface | Implemented changes | Still required |
| --- | --- | --- |
| Connectors list / inspector | Existing selected identity, authorization, capability catalog and agent dependencies retained. Selected inspector opens in a labelled, scrollable 540px maximum sheet below 1024px. Configure/reconnect closes the sheet before opening the next flow. Keyboard row selection and phone action targets retained/enlarged. | 1440/834/390 render, focus return, live permission/reconnect/sync states |
| Sources inventory / inspector | Desktop comparative table retained. Below 1024px, compact source rows disclose status, environment, tables, records, workflow count and sync time. Selection opens a source sheet; desktop retains inline context. Full reported schema names, health gauge/value, operator usage, sync/delete confirmation, details and source-to-workflow handoff retained. Attention selection works independently of category/stage filters. | Rendered geometry, real inventory/ingestion, mutation permissions, persisted source workflow creation |
| Sources truth / freshness | Missing or unfamiliar status is unknown, never implicitly connected. Missing health remains unreported. Freshness updates on successful fetch, not every render. | Owner response shapes and freshness/recovery walk |
| Approval request / phone dock | Display typography, wrapping request values, 44px queue-return target, extra content clearance. Shared action-dock marker moves AI launcher above mounted Marketplace/Approval controls; approval-specific clearance also applies below 1024px. Approval/rejection backend operations and rejection confirmation retained. | Phone/tablet geometry, decision persistence and execution handoff |
| Capture harness | Added real-page Sources and Metrics shot routes. Sources fixture includes connected, syncing and failing inventory; Analytics fixture includes run volume, P50/P95/P99 latency and throughput. Explicit screenshot-only payloads. Existing production harness/auth restrictions unchanged. | New fixture screenshots; fixtures are not live tenant proof |

Seven new behavioral tests cover unknown status, full tablet source/schema/workflow context, selected sync/delete targeting and confirmation, failed inventory retry, tablet connector readiness disclosure, close-before-configuration and inline desktop inspection. The prior structural IA test now recognizes the responsive inspector wrapper; its other discovery/table/capability assertions remain intact.

Final local verification: full Vitest **1,166 passed / 193 files**; production Next.js build **PASS**; TypeScript **PASS**; full ESLint **0 errors / 275 existing warnings**, final changed-file lint **0 errors**; chat/status/intelligence/brand guards **PASS**. Cognitive guard reports **PASS** with Python import smoke and targeted pytest explicitly skipped. Whitespace check **PASS**. The first build failed on a corrupt Turbopack cache; a clean-cache build and the subsequent final-code build both passed. No lockfile or dependency change.

Browser check: local fixture URL rejected with `net::ERR_BLOCKED_BY_CLIENT`. A dev-server attempt also failed on this environment's `uv_interface_addresses` system call; it was stopped. No new browser screenshot or visual acceptance is claimed. Added capture routes are implementation, not captured evidence. OWNER_LIVE_ACCEPTANCE = NOT_RUN. IMPLEMENTATION_COMPLETE = NO. MERGE_READY = NO pending remaining implementation, rendered route/state evidence, owner requirements and candidate CI. CAUGHT_UP = NO. Draft continuation PR remains unmerged; no production deployment performed.

## Workflow list continuation — 2026-10-04 UTC

Base published connection/source patch: `5f0f6c444065321bb7e317d3b84cdb65bd266836`, tree `29cda05c47e710c095b74252f6b45d3a3946290a` (matches the tested local tree). Its GitHub Web, runtime gate and dependency audit passed; Marketing Lighthouse passed. Backend/integration completion was still pending at this inspection. Those checks do not establish this follow-up candidate.

Workflows retains the existing phase controls, grid/table selection, search, filters, workflow cards/table, editor/run-history links, duplication, delete confirmation and status mutations. Its organization summary is now shared across Table and Grid, stacks on phones, and explicitly states that totals are independent of list filters. Missing/non-finite server stats remain unreported; actual zero metrics display as zero. Successful execution remains distinct from verified business outcomes. Freshness uses successful fetch time. Decorative radial atmosphere and card-entry spring/stagger are removed; view transitions use 180ms or no motion under reduced-motion preference. This applies Figma handoff `22:2`, not an unseen Workflows pixel reference.

Final local suite: **1,168 passed / 194 files**, including two new metric-truth/scope tests. Final production build and its TypeScript phase **PASS**. Changed-file lint **0 errors / 2 existing Workflow import warnings**; preceding full lint had 0 errors / 275 warnings. Chat/status/intelligence/brand guards and whitespace check **PASS**. The first incremental follow-up build encountered the same corrupt persisted Turbopack cache; final clean-cache build passed. A missing retained icon import was caught by TypeScript and restored before the final checks. No dependency/lockfile changes; restored MSP post and hero remain present.

No new screenshot or owner acceptance. Existing browser block remains; no rendered geometry is claimed. IMPLEMENTATION_COMPLETE = NO; OWNER_LIVE_ACCEPTANCE = NOT_RUN; MERGE_READY = NO; CAUGHT_UP = NO. Final candidate GitHub CI remains a separate required check. No merge or production deployment.

## Audit of ChatGPT connection/workflow claims — 2026-10-04 UTC

Reviewed published head `ee683941` on draft PR #298. The claimed Connectors sheets, Sources compact rows/unknown status/actions, Approvals wrap + dock clearance, Workflows dual-view totals, and Sources/Analytics shot routes **are implemented on the branch**. GitHub Web, Shared runtime, Lighthouse, Dependency audit and Vercel preview **passed** on `ee683941`; Billing E2E stayed skipped. That is verified by automated checks, not visual or owner acceptance.

Applicable gaps found and fixed on this follow-up (not a full-suite re-run of the claimed 1,168):

| Gap | Fix |
| --- | --- |
| Desktop source inspector still sat under the inventory | Inspector now renders in the operations column at ≥1024px; tablet/phone keep the sheet |
| Omitted tables/records/usage became `0` | `normalizeSource` keeps nulls; UI shows `Not reported`; actual zeros remain zeros |
| Unknown status had no table indicator | Muted status dot for unknown |
| Compact source rows could not deselect | Toggle matches the desktop table |
| Sources category motion ignored reduced-motion | Same 180ms / no-motion treatment as Workflows |
| Workflow table wrapper used `overflow-hidden` | `overflow-x-auto` so AdaptiveDataView can scroll at tablet widths |

Focused tests: 11 passed across source, connector and workflow files. Visual/owner acceptance remain NOT_RUN. IMPLEMENTATION_COMPLETE = NO. MERGE_READY = NO. CAUGHT_UP = NO. Not merged. Not production deployed.

## Notification inbox and audit continuation — 2026-10-04 UTC

Base: Cursor follow-up `f86ca547d33ac6f33d0f3f8ec75b3eccc78b2bb7`. Its source count/desktop inspector, compact selection, unknown-status and reduced-motion fixes remain intact. This pass does not reinterpret the synchronize event as a failed CI run.

Figma Operate specimen `10:101` was read with design context and its screenshot. Notifications and Audit adapt its quiet rows, short status text and open operating header; neither has a separate inspected pixel specimen. Shared Emerald tokens and responsive handoff rules are retained. This establishes implementation direction, not a rendered pixel match.

| Surface | Changes on this candidate | Remaining evidence |
| --- | --- | --- |
| Notifications | Separate destination links from read/delete controls. Wrap titles/body/metadata on phones, keep controls visible on touch, and use 44px targets. Explicit Read/Unread text; type selection replaces ten wrapping pills. Loading, error/retry, cached error and true empty states are distinct. Missing unread counts/time remain unreported. Inbox-wide unread count is separate from the 200 loaded results and today within those results. | Phone/tablet/desktop screenshots, owner inbox/permissions, live bell propagation |
| Notification mutations | Serialize rapid/repeated operations. Opening an already read row does not reduce unread count. Unread filters exclude newly read rows. Archive loaded removes only successful requests, retains failed rows, reports partial failure and subtracts only removed unread items. Successful archives do not zero unread outside the loaded batch. Read-all/delete and settings/destination routes retained. | Live persistence, cross-surface cache refresh and owner recovery walk |
| Audit | Preserve event summaries, outcomes, actor/entity context, technical JSON and real CSV/JSON exports. Flat rows with wrapped phone content and accessible technical disclosure. Loading/errors do not become empty logs or zero summary users; summary failure has its own retry. Matching totals include range/action/entity; actor summary uses range only. Search/export scope disclosed. Pagination survives zero search matches and failed subsequent pages. Freshness attaches to successful fetch, not render. Export controls have mobile accessible labels, 44px targets and in-flight protection. Reduced motion removes entry translation/stagger. Access errors do not assert that upgrading is the only remedy. | Rendered geometry, real audit filters/export/authorization, owner freshness and recovery walk |

Seventeen new component behavior tests cover these states/mutations. Focused suite **17/17 PASS**. Full suite with `TZ=UTC`: **1,187 passed / 196 files**. Initial shell-default run (`TZ=Asia/Tokyo`) had **1,185 pass / 2 failures** in unchanged chat recency/history tests that compare UTC fixtures against local calendar boundaries. Those nine tests passed under UTC; no chat code or timezone configuration was modified to mask the assumption.

Clean-cache production build **PASS (exit 0)**, including TypeScript and all 371 static pages; final standalone TypeScript **PASS**. Full ESLint **0 errors / 273 existing warnings**; changed files **0 errors / 0 warnings**. Chat/status/intelligence/brand guards and whitespace check **PASS**. Cognitive guard **PASS**, with Python import smoke and targeted pytest explicitly skipped. No dependency, lockfile or build configuration changes.

No new browser screenshot, live tenant verification or owner acceptance. Existing local browser/network restriction remains unresolved. Candidate GitHub CI is separate from local checks and must be inspected on the published commit. IMPLEMENTATION_COMPLETE = NO; VISUAL_ACCEPTANCE = NOT_RUN; OWNER_LIVE_ACCEPTANCE = NOT_RUN; MERGE_READY = NO; CAUGHT_UP = NO. Draft PR #298 remains unmerged. No production deployment.

## Settings navigation and persistent forms — 2026-10-04 UTC

Base: `ca36de5cb160a017c0566b9e9b54875caeec4acf`. Its CI jobs Web, Backend, Shared runtime, Dependency audit and Integration Smoke were independently inspected as completed/success; Marketing Lighthouse completed/success. Billing E2E was skipped. These base checks do not certify this new candidate.

Figma handoff `22:2` was read with high-fidelity design context and its screenshot. The Settings implementation applies focused configuration, shared Emerald tokens, tablet sheets, phone disclosure, 44px action targets and reduced motion. No dedicated Settings pixel specimen was inspected; no new rendered visual match is claimed.

| Area | Implemented changes | Outstanding evidence |
| --- | --- | --- |
| Shared Settings shell | Desktop grouped sidebar remains at >=1024px; below that, a labelled scrollable sheet replaces the in-flow mobile grid and tablet sidebar. Sheet uses local state when standalone routes do not supply controlled state, fixing inaccessible navigation on Profile/Organizations and other standalone consumers. Real hrefs, tier grouping, active-section indication and admin section filtering remain. Navigation closes the sheet; Radix close returns focus; desktop resize closes it. Long labels wrap, links/trigger/close reach 44px, default titles use display font, and own-hero pages avoid a duplicate heading. | Desktop/tablet/phone geometry, real route navigation/role walk, focus behavior in supported browsers |
| Organization form | Initial loading/missing/error states block blank writes and expose retry. Name, slug, domain and logo URL come from the reported organization. Drafts survive a background update; component resets on organization identity change. Field labels and keyboard form submission are accessible, fields/actions disable for non-admins or pending writes, and errors stay inline. Saves include the existing logo because the endpoint otherwise clears it. Image URL edits persist through the existing update endpoint; invalid edits do not break the preview or reach save. | Owner-org save/refetch, backend authorization, image geometry. File upload remains unimplemented and is explicitly described as unavailable; the previous dialog's controls had no upload handler |
| Organization notification preferences | Fetch actual `/api/settings/notifications` preferences before editing; remove sample Acme recipients. Loading, malformed/missing response and fetch failure block edits with retry. Save channel toggles and validated, deduplicated recipient arrays to that endpoint's PATCH shape rather than the incompatible generic settings request. Report saved only after a successful response with preferences. Failed writes stay inline, rapid submissions serialize, and admin/owner control matches organization-level configuration. | Owner preferences persistence, backend permission/RLS enforcement and actual email/Slack delivery |
| Slack setup | Saved Slack preference remains separate from connection readiness. Replace the non-persistent webhook/channel/alert-type dialog with a real `/connectors` handoff. No Slack connection or successful delivery is inferred from the preference. | Owner Slack authorization/configuration and delivery run |
| Shared sheet primitive | Overlay/content suppress entrance/exit animation under reduced motion. Existing consumers and API are retained. | Reduced-motion browser rendering on representative consumers |

New focused suite: **20 passed / 3 files**, covering standalone navigation, href close, focus return, tablet-to-desktop close, own-header composition, loaded forms, permission guards, inline failure, draft/logo preservation, malformed preferences, recipient validation and repeated-submit protection. Full Vitest under `TZ=UTC`: **1,207 passed / 199 files**. UTC matches the existing chat recency fixtures' assumptions documented in the previous pass; no timezone configuration or chat code changed.

Clean-cache production build **PASS (exit 0)**, final standalone TypeScript **PASS**, full ESLint **0 errors / 271 existing warnings**, changed-file ESLint **0 errors / 1 existing unused BillingUsageSettings warning**. Chat/status/intelligence/brand guards and whitespace **PASS**. Cognitive guard **PASS**, with Python import smoke and targeted pytest explicitly skipped. No dependency, lockfile, database, backend route or build configuration changes.

This is implementation and automated evidence. No new browser screenshot or owner-live acceptance was performed; the previously recorded local browser/network restriction remains unresolved. Other Settings forms and billing behavior still require their own route/state review. Candidate GitHub CI must be inspected independently on publication. IMPLEMENTATION_COMPLETE = NO; VISUAL_ACCEPTANCE = NOT_RUN; OWNER_LIVE_ACCEPTANCE = NOT_RUN; MERGE_READY = NO; CAUGHT_UP = NO. Draft PR #298 remains unmerged; no production deployment.

## Settings remaining forms — 2026-10-04 UTC

Base: `1cce2b48`. Organization and notification forms from that commit were kept. Remaining in-page forms were extracted or corrected so they cannot present unsaved local state as persisted product settings.

| Form | Change | Still required |
| --- | --- | --- |
| Security / SSO | Real SSO load/save/enable/disable/delete/test kept. Action row wraps. Missing `provider_type` no longer crashes. Organization-wide 2FA Enable and IP allowlist Save were removed — those have no settings API. | Owner SSO round-trip |
| Team | Loading/error/retry, compact cards below `md`, 44px actions, viewer role on edit. Invite/update/remove still use `/api/settings/team`. | Owner invite/remove |
| API keys | Loading/error/retry, named create, per-key rotate/revoke, one-time revealed value when the API returns it. | Owner create/rotate |
| Webhooks | Admin-gated fetch, loading/error/retry, wrapping URLs, honest status text. Create/delete APIs unchanged. | Owner delivery |
| AI Models | Fake workspace-default Save removed. Memory entity matching remains the persisted policy. | Owner embeddings save |
| Lite seats / Meson addons | Loading/error/retry and admin copy. Existing department/addon/voice APIs unchanged. Meson prices still come from the API, not invented here. | Owner allocation/billing |

Focused Settings tests: 21 passed. Typecheck exit 0. Visual/owner-live remain NOT_RUN. Model Studio, Plays, Training, Schedules, AI workspace, and fixture visual verification were not completed in this pass. IMPLEMENTATION_COMPLETE = NO. MERGE_READY = NO. CAUGHT_UP = NO.

## Required CI restore + remaining design coverage — 2026-10-04 UTC

Reviewed PR head was still `7e9832c6` after fetch. Required Web failed on `phase-3-product-ia.test.ts` expecting “AI Operator” in `app/settings/page.tsx`. Prompt3 failed `npm ci` because root `package-lock.json` still listed `shadcn@4.10.0` as a dependency while `package.json` declared `shadcn@^4.21.0` as a devDependency. That drift existed on `main`; this PR triggered Prompt3 by touching `settings-sections.ts`.

| Area | Implemented | Disposition |
| --- | --- | --- |
| Settings IA test | Asserts extracted composition, notification rows, SSO Enable/Disable row chrome, honest AI Models (Memory embeddings, no ModelSelector / “AI Operator”) | Verified by automated checks |
| Prompt3 lockfile | Regenerated root `package-lock.json` only; `shadcn@4.21.1` now satisfies `^4.21.0`. No other package.json range changes | Verified locally by `npm install --package-lock-only`; GitHub Prompt3 pending published SHA |
| Plays | Operate rows, empty state, `TYPE.eyebrow`, no elevated `--np-shadow` cards; detail/setup/results flattened; missing required approvals render “Not reported” | Implemented on branch |
| Metrics | Omitted overview/throughput stay unreported; overview SWR error/retry; charts retained | Implemented on branch |
| Environments | Health, resource counts, API URL, created/last-activity no longer invented as 100 / 0 / “Just now” | Implemented on branch |
| Training | `WorkSectionErrorCard`, loading vs empty, freshness on successful fetch, `pb-20` MobileBottomNav clearance | Implemented on branch |
| Model Studio | List/job/dataset fetch error/retry; missing built-in sufficiency labeled “Not reported” | Implemented on branch; tablet sheet still not wired |
| Schedules | Workflow schedules `data-composition="operate"`; `ScheduleDetailSheet` remains unused | Partial |
| Multi-agent run | `data-composition="manage"` | Supporting |
| AI workspace | Embedded `ChatWindowControls` `openAsFloat`; user expand/fullscreen/collapse/mobile mode changes go through `choosePresentationMode` | Implemented on branch; docked Playwright and owner stream remain unverified |

Local checks on this working tree: Vitest **1215 passed / 200 files**; ESLint **0 errors / 271 existing warnings**; `tsc --noEmit` **0**; `pnpm build` **0** (371 routes); chat-surface, status-leak, intelligence-surface, brand, cognitive guards **PASS** (targeted pytest skipped). Billing E2E remains `workflow_dispatch` only — skipped is not passed.

Visual: NOT_RUN for this SHA. `localhost:3055/e2e/shots/metrics` rendered a fixture overlay plus Next error chrome on a stale server; `/plays` then failed with `chrome-error://chromewebdata/`. Viewport matrix 1440/834/390 was not completed. Capture is not evidence for the published SHA. Owner-live: `https://gravitre.app/login` (session expired / no authorized owner session used). Isolated Conversation Smoke is not owner-tenant evidence.

Kept explicit: organization logo file upload unavailable; Slack/email delivery unverified; Finance department and Compliance packs product-scope gaps; frontend permission ≠ backend authorization.

IMPLEMENTATION_COMPLETE = NO. VISUAL_ACCEPTANCE = NOT_RUN. OWNER_LIVE_ACCEPTANCE = NOT_RUN. MERGE_READY = NO. CAUGHT_UP = NO. Draft PR #298 remains unmerged. No production deployment.

## Design-led surface review — 2026-10-04 UTC

Starting published head: `72caac273010d564aa1e93d16dbfb458c0099ddc`. User requested intentional primary/secondary/tertiary coverage and design leadership. Retrieved Figma handoff `22:2` with high-fidelity context and screenshot; reused page-03 token provenance and the five composition families.

Review queue: `docs/design/3.0-plus/18-design-surface-review-queue.md`, regenerated by `scripts/inventory-design-surfaces.py`: 175 page routes and 361 reachable control/disclosure source files. This is static discovery, not evidence that every surface has been manually or visually reviewed. Detailed direction, source findings and queued review order: `docs/design/3.0-plus/19-design-led-review.md`.

Implemented: Model Studio compact intent and dataset preview sheets, provider/search/inspect retry, reported file/progress values; schedule compact sheet using the existing occurrence-aware action flow; 44px shared window close controls, reduced-motion dialogs/confirmations and 200ms sheet entry; Lite tasks/deliverables operating rows, narrow-layout action reflow, pending cancellation/download, unknown status and fetch retry; Lite Results reported/unknown KPIs and ruled evidence lists. APIs and runtime behavior remain canonical.

Automated evidence: full Vitest with `TZ=UTC` 1,228 passed / 203 files; four added schedule tests cover 390/834/1440 presentation and real-action confirmation, nine added inspector/Lite tests cover selection, focus return, resize, missing values, failure/retry and duplicate cancellation. Typecheck exit 0; production build exit 0 (371 routes); full ESLint 0 errors / 270 warnings. Chat-surface, status-leak, intelligence-customer-surface and brand guards PASS. These are local checks, not GitHub CI on the follow-up commit.

Visual browser evidence: localhost fixture blocked by `net::ERR_BLOCKED_BY_CLIENT`; published preview redirected to Vercel login. No product-screen walkthrough or pixel parity is claimed. `VISUAL_ACCEPTANCE = NOT_RUN`; `OWNER_LIVE_ACCEPTANCE = NOT_RUN`; `IMPLEMENTATION_COMPLETE = NO`; `MERGE_READY = NO`; `CAUGHT_UP = NO`. Remaining review includes Assignments/Goals, nested Agents/Models/Training, Marketplace/admin, Workflows/builder/runs and AI/Settings nested states per the queue. Draft #298 stays unmerged and is not production-deployed.

## Assignment and Goal detail continuation — 2026-10-04 UTC

Starting published head: `a388e0e7b6d5c0fb3b2f0f1967ef78d5c59f95fc`. Source review found a fixed 420px assignment work column competing with preview at compact widths, idle looping glow/pulse motion, local-only per-deliverable approval markers and synthesized successful execution phases when no trace existed.

Assignment detail: trace and ruled output queue with desktop adjacent preview; tablet/phone selection-driven sheet; keyboard-accessible selection/review buttons; 44px actions; wrapping content; scrollable decision/edit windows; reduced motion and quiet idle states. Preview failure is scoped to the task and preserves returned output. Failed refresh preserves cached work with retry. Missing execution trace/progress remain unreported, rather than presenting synthesized successful phases. Self-reported confidence preserves real zero, remains unverified, and invalid values stay unreported.

Approval behavior: local approval markers removed. Review buttons open the existing assignment-wide approval/rejection flow; approved state derives from the returned handoff. API errors stay in the window. Pending decisions disable actions/dismissal, and review opened by the URL can be dismissed without a decision. Recommendation previews do not imply that the primary-response editing/push endpoints apply to them. Destination `ok:false` cannot produce a success message. Rejection copy confirms a saved decision, not delivery to the agent. Existing APIs remain unchanged; no claim of backend permission verification.

Goals detail: ruled progress band and ordered milestones rather than a repeated elevated card stack. Shared display typography and semantic colors, wrapping status badges, actual zero vs missing progress/milestones, reduced-motion progress and cached evidence retained on refresh error.

Automated checks: full Vitest with `TZ=UTC`: 1,240 passed / 204 files, including 12 new detail-flow tests. Typecheck/build passed; production build generated 371 routes. Full ESLint 0 errors / 268 existing warnings; changed-file ESLint 0 errors. Chat-surface, status-leak, intelligence-customer-surface and brand guards PASS. A repeat build hit corrupted local Turbopack cache; cache moved aside and clean build passed. No application fix or dependency change was needed for that cache failure.

Regenerated surface queue: 175 page routes / 362 reachable control/disclosure source files. Detailed disposition remains in `docs/design/3.0-plus/19-design-led-review.md`. Assignment creation, Goals list, nested Agents/Models and the rest of the review queue remain open.

No current rendered screenshots or owner-live execution evidence were added. `VISUAL_ACCEPTANCE = NOT_RUN`; `OWNER_LIVE_ACCEPTANCE = NOT_RUN`; `IMPLEMENTATION_COMPLETE = NO`; `MERGE_READY = NO`; `CAUGHT_UP = NO`. New GitHub CI is separate from local checks. Draft PR #298 remains unmerged and is not production-deployed.

# Gravitre 3.0 Extrovert Design — completion ledger

Started: 2026-10-03  
Base: `origin/main` `2b39b87b` (PR #297 Emerald Intelligence migration, merged)  
Active branch: `feat/gravitre-3.0-extrovert-design`  
Reason for new branch: `feat/emerald-intelligence-completion` / PR #297 is merged. This is the single continuation branch for Extrovert completion + Figma Brand Foundation alignment.

Figma file:  
https://www.figma.com/design/OsDKeRy9HwfSKR3e9YyOFM/Gravitre-%E2%80%94-Brand-Foundation---Creative-Direction?node-id=6-2

## Figma capability check (this session)

Live tool catalog was searched for `figma` (no prefix assumed). Result: **no Figma namespace and no Figma tools**. Available MCP namespaces did not include a Figma server. Settings enablement was not treated as availability.

| Value class | Used? | Notes |
| --- | --- | --- |
| Exported Figma variables | NO | No MCP export this session |
| Inspected fills | PARTIAL | Browser view of page 03 Marketplace `8:2` and Intelligence `10:5` only; unsigned Figma, no variable panel export |
| Written contract + first `:root` | YES | Current documented tokens preserved until an authoritative Figma export corrects them |

## Brand Foundation tokens (applied)

Source: written contract + first `:root` in `globals.css` (PR #297). Hexes match that contract. Later Carbon `:root` had been overwriting them with `#2fbf8f` / Ion violet. No exported-variable correction this session.

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

Pages observed:

| Page | Status |
| --- | --- |
| 01 — Brand Foundation | Tokens recorded above; MCP hex export still unavailable |
| 02 — Gravitre Unlocked | Listed; not pixel-inspected |
| 03 — Emerald Intelligence (current) | Marketplace `8:2`; Intelligence `10:5` (1440×900); Operate next |

Implementation frames on page 03:

- GRAVITRE / EMERALD INTELLIGENCE (node `6:3` — agent identity studies: Guardian / Atlas)
- IMPLEMENTATION / Marketplace 3.0 Desktop (node `8:2`, 1440×1040)
- IMPLEMENTATION / Marketplace 3.0 Mobile
- IMPLEMENTATION / Intelligence
- IMPLEMENTATION / Agents
- IMPLEMENTATION / Operate
- IMPLEMENTATION / Builder
- IMPLEMENTATION / Analytics + Visualization System
- IMPLEMENTATION / Tokens + Components + Responsive
- IMPLEMENTATION / Responsive Product Studies
- IMPLEMENTATION / Handoff + Acceptance
- IMPLEMENTATION / Graphic + Motion Language

`VOICE_LIVE_*` and RLS / Lighthouse follow-ups stay out of this stream.

## Gate snapshot

| Field | Value |
| --- | --- |
| ACTIVE_BRANCH | `feat/gravitre-3.0-extrovert-design` |
| COMPLETION_PR | [draft #298](https://github.com/cesarbohjr/gravitre-saas-backend/pull/298) |
| CANDIDATE_SHA | `77ca50ce` |
| IMPLEMENTATION_COMPLETE | NO |
| AUTOMATED_CHECKS | IN_PROGRESS on `77ca50ce` (local `tsc --noEmit` passed; GitHub CI not terminal) |
| BILLING_E2E | NOT_APPLICABLE (no billing scope in this slice) |
| OWNER_LIVE_ACCEPTANCE | NOT_RUN |
| MERGE_READY | NO |
| MAIN_SHA | `2b39b87b` |
| DEPLOYED_SHA | unverified this session |
| PRODUCTION_VERIFIED | NO |
| CAUGHT_UP | NO |
| OUTCOME_VERIFIED | not claimed |

## Route inventory

`route | composition family | nested surfaces | current gap | implementation files | verification required | evidence type | tested SHA | status | blocker`

| route | family | nested | current gap | files | verification | evidence | SHA | status | blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/home` | Understand | KPI, time, drill-down | Owner-live metrics not re-checked after #297 | `components/home/home-dashboard.tsx` | owner metrics + time controls | owner-live | — | IMPLEMENTED / BRANCH (prior) | OWNER_LIVE |
| `/ai` | Create | composer, history, tools | Protected chat seams — visual only | `app/ai/page.tsx` | stream + persist | owner-live | — | PARTIAL | auth + protected seams |
| `/agents` | Manage | list, inspector | Glow fallbacks removed; identity green/blue on Brand Foundation tokens | `app/agents/page.tsx`, `components/agents/fleet-v4/identity-tokens.ts` | list/detail consistency | visual + owner | — | IN PROGRESS | OWNER_LIVE |
| `/agents/[id]` | Manage | tabs, autonomy | Default glow/gradient no longer brand-shadow | `app/agents/[id]/page.tsx` | save persist | owner-live | — | PARTIAL | OWNER_LIVE |
| `/connectors` | Manage | catalog, instance | Connection status must stay real | `app/connectors/page.tsx` | reconnect path | owner-live | — | PRIOR | OWNER_LIVE |
| `/sources` | Manage | ingest, detail | Readiness honesty | `app/sources/page.tsx` | inventory | owner-live | — | PRIOR | OWNER_LIVE |
| `/workflows` | Operate | list, builder | Composition retagged operate; Brand Foundation phase/metrics | `app/workflows/**` | safe run | owner-live | — | IN PROGRESS | OWNER_LIVE |
| `/intelligence` | Understand | map, rails, model studio | Indigo map stubs removed; core aura uses Brand Foundation; idle no pulse | `app/intelligence/**` | filters + evidence | owner-live | — | IN PROGRESS | OWNER_LIVE |
| `/marketplace/assets` | Discover | types, install | Mobile search-first + desktop outcomes-first implemented; catalog cards now treat department packs as outcome tiles; grouped pack contents | `app/marketplace/assets/**` | install + runtime id | fixture + owner-live | — | IN PROGRESS | catalog/runtime proof + OWNER_LIVE |
| `/marketplace/assets/[slug]` | Discover | detail, readiness, sticky install | Discover chrome, grouped contents, pipeline when department present, sticky mobile install; Sparkles removed | `app/marketplace/assets/[slug]/page.tsx` | prerequisites + install | fixture + owner-live | — | IN PROGRESS | OWNER_LIVE |
| `/approvals` | Operate | queue | Actor/context | `app/approvals/page.tsx` | approve/reject | owner-live | — | PRIOR | OWNER_LIVE |
| `/activity` | Operate | runs | Execution state | `app/activity/page.tsx` | run vs activity | owner-live | — | PRIOR | OWNER_LIVE |
| `/audit` | Configure | events | Real org events | `app/audit/page.tsx` | filters | owner-live | — | PRIOR | OWNER_LIVE |
| `/settings/**` | Configure | billing, team, profile | Billing E2E separate | `app/settings/**` | save + entitlements | billing e2e | — | PRIOR | billing e2e |
| `/plays` | Operate | play, results | Not invented this sprint | `app/plays/**` | real play data | owner-live | — | PRIOR | — |
| `/admin/intelligence` | Understand | admin tabs | Glow/hover remnants | `app/admin/intelligence/**` | admin-only | owner-live | — | GAP | role gate |
| marketing `/*` | Discover | purple legacy | Decorative purple on legacy feature pages | `app/(marketing)/**` | visual | fixture | — | GAP | not Talk-blocking |

Hidden / legacy (reachable, do not invent new paths): `/operator`, `/command-center`, `/chat`, `/assistant`, `/tasks`, `/systems`, `/admin/intelligence`, `/training`, `/multi-agent-run`, `/metrics`, `/outcomes` → activity.

## Department pack matrix

From `backend/app/marketplace/department_pipelines/catalog.py` (do not invent packs):

| Pack slug | UX/UI complete | Pack content complete | Notes |
| --- | --- | --- | --- |
| `revenue-operations-pack` | PARTIAL (shared catalog/detail/install/installed/pipeline chrome) | UNVERIFIED | Nested UX implemented on shared surfaces; live pack rows not owner-inspected |
| `marketing-operations-pack` | PARTIAL (shared surfaces) | UNVERIFIED | Same shared chrome; no invented pack |
| `hr-operations-pack` | PARTIAL (shared surfaces) | UNVERIFIED | Same shared chrome; no invented pack |
| `msp-operations-pack` | PARTIAL (shared surfaces) | UNVERIFIED | Same shared chrome; no invented pack |
| (pipeline with `default_department_pack_slug=None`) | N/A | N/A | Honest gap in catalog |

PR #297 removed several marketplace3 certification/portfolio modules and capability_package skill trees from `main`. Treat “six remaining packs complete” from older chat as **historical, not current**. Re-verify catalog + install identifiers on this SHA before any ready/outcome badge.

## Inspection vs unverified vs login-blocked

These rows stay in the acceptance checklist. **None are passed.** Isolated Conversation Smoke is not owner-tenant evidence.

| Surface | Actually inspected | Visually unverified | Owner tasks blocked by login |
| --- | --- | --- | --- |
| Marketplace catalog `/marketplace/assets` | Code + unsigned Figma frame `8:2` (1440×1040) + login redirect on `gravitre.app` and `127.0.0.1:3010` | Authenticated catalog grid, live pack cards, install counts, mobile search-first with real data | Browse live catalog; filter department packs; install; confirm runtime IDs |
| Marketplace detail `/marketplace/assets/[slug]` | Code (Discover chrome, grouped contents, sticky bar, pipeline hook) | Live pack detail, readiness checklist, sticky install, failure toast | Open each real department pack; install/readiness/failure |
| Marketplace installed | Code (operate composition, inspector, pipeline) | Live installs, deep links, uninstall | Confirm owner-org installs and evidence |
| Agents `/agents` + `/agents/[id]` | Code (glow fallbacks removed; identity green/blue rematched; stored avatar IDs untouched) + prior unsigned Agents frame | Authenticated list/inspector, personality tiles, save persist | List + detail save + history |
| Intelligence `/intelligence` | Code (indigo stubs removed; Brand Foundation aura; idle no pulse) + unsigned frame `10:5` (1440×900) | Live map, rails, filters, evidence | Values / filters / evidence on owner org |
| Operate `/workflows` + runs/activity/approvals | Code (composition retagged; builder Create chrome present; run-path glow left functional) | Live queue, run states, builder persist, safe run | Persist + approved safe run; decision queue |
| Builder | Code inspection of nav/inspector/canvas; functional SVG glow left on active run only | Pixel match vs page 03 Builder frame (Figma MCP unavailable) | Builder persist + run |
| Analytics `/metrics` + Intelligence performance | Code (Understand composition; ChartTooltip; completed stroke rematched) | Charts with live metrics | Dashboard / metrics time + drill-down |
| Handoff / Motion | Approvals already Decision queue; decorative install glow/Sparkles removed; marketing motion-safe hovers | Page 03 Handoff + Motion frames not MCP-inspected | Owner walk of Lock→Route→Handoff→Resolve where those states exist |

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
- Billing: separate workstream

## Fixture visual evidence (not owner-live)

Candidate SHA `77ca50ce`. Preview: `https://gravitre-saas-backend-isq7czh5j-gravitre-ai.vercel.app` (Vercel READY).

| Check | Result | Class |
| --- | --- | --- |
| Marketing `/` desktop | Rendered on preview; Brand Foundation emerald heading, no page-theme purple | fixture |
| Marketing `/features` desktop | Coordinate → Act → Approve → Resolve present; no invented prices | fixture |
| Marketing `/features` 390×844 | Stacked header, wrapping chips, cookie sheet; layout holds | fixture-responsive |
| Product `/marketplace/assets`, `/agents` | Preview redirects to `https://gravitre.app/login` | login-blocked |
| `/e2e/shots/agents` on preview | 404 (shot routes not in this preview build) | fixture unavailable |
| Local typecheck | `npm run typecheck` in `apps/web` exit 0 | automated-local |
| Isolated Conversation Smoke | Not used | n/a |

## Next concrete actions

1. Owner sign-in required for authenticated Marketplace / Agents / Intelligence / Operate pass. Isolated Conversation Smoke org is not owner proof.
2. Figma remains absent from the live tool catalog. Preserve documented tokens until an exported-variable pass exists.
3. Wait for required CI on `77ca50ce`; fix failures on this same PR.
4. Remaining owner-access tasks are listed in the inspection table — none are passed.

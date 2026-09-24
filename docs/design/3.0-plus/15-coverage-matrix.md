# 15 — Coverage matrix (§43)

**Status:** Living gate — not complete until every route has disposition + evidence.  
**Source inventories:** `02-route-interaction-inventory.md` · master §§28–30 · `apps/web/app/**/page.tsx` walk (2026-09-23).  
**Companion:** Phase 6 harness validation slots → `16-phase6-validation-notes.md`.  
**Rule:** No broad redesign complete while important routes remain unaccounted for.  
**Scope note:** Marketing `(marketing)/*`, `api/`, and heavy `e2e/*` shot pages omitted from rows below (tracked in inventory only).

| Route / family | Experience family | User job | Existing capability | Current defects (summary) | Design disposition | Impl phase | Test / visual | Completion evidence |
|----------------|-------------------|----------|---------------------|---------------------------|--------------------|------------|---------------|---------------------|
| `/ai` + float shells | Core / Ask | Intent + work | Custom AI runtime | Dual Meson/Ask chrome; docked missing | Shared-system update + WM | P8 after G-STRUCT | NOT PROVEN | — |
| `/ai/help/control` | Core / Ask | Control help | Nested AI help | Likely template chrome | Shared-system update | P8 | NOT PROVEN | — |
| `/chat` `/assistant` | Core / Ask | Legacy / assist entry | Alternate chat surfaces | Dual-path risk vs `/ai` | Consolidate toward `/ai` | Defer / P8 | NOT PROVEN | — |
| `/activity` | Core | Observe TRACE | Activity TRACE | Composition density | Shared-system update | P8 | NOT PROVEN | — |
| `/approvals` | Core | Approve WRITE | Approvals queue | Density; continue path unproven | Shared-system update | P8 | NOT PROVEN | — |
| `/notifications` | Core | Notice | Notification list | Header monoculture risk | Composition improvement | P8 | NOT PROVEN | — |
| `/audit` `/metrics` | Core / admin | Audit / metrics | Audit + metrics pages | Density; not journey-proven | Shared-system update | P8 | NOT PROVEN | — |
| `/assignments` | Core | Own outcomes | Assignments list | Confidence display bugs | Composition improvement | Defect now / P8 | NOT PROVEN | — |
| `/assignments/new` | Core | Create assignment | Create form | Form chrome sameness | Shared-system update | P8 | NOT PROVEN | — |
| `/assignments/[id]` | Core | Assignment detail | Detail + actions | Empty / honesty defects possible | Composition improvement | Defect now / P8 | NOT PROVEN | — |
| `/goals` | Core | Track goals | Goals list | Empty goals UX weak | Composition improvement | Defect now / P8 | NOT PROVEN | — |
| `/goals/[id]` | Core | Goal detail | Goal detail | Under-specified composition | Composition improvement | P8 | NOT PROVEN | — |
| `/home` | Core | Orient | Home dashboard | KPI card risk | Composition improvement | P8 | NOT PROVEN | — |
| `/lite` | Core | Lite orient | Lite shell | Secondary product path | Composition improvement | P8 | NOT PROVEN | — |
| `/lite/tasks` | Core | Lite tasks | Task list | Lite vs full parity unclear | Composition improvement | P8 | NOT PROVEN | — |
| `/lite/assign` | Core | Lite assign | Assign flow | Nested lite chrome | Shared-system update | P8 | NOT PROVEN | — |
| `/lite/deliverables` | Core | Lite deliverables | Deliverables list | Card catalogue risk | Composition improvement | P8 | NOT PROVEN | — |
| `/lite/results` | Core | Lite results | Results surface | Honesty / empty states | Composition improvement | P8 | NOT PROVEN | — |
| `/agents` | Agents | Browse roster | Agent list | Header monoculture | Interaction redesign gated | P8 | NOT PROVEN | — |
| `/agents/new` | Agents | Create agent | Create form | Template form risk | Shared-system update | P8 | NOT PROVEN | — |
| `/agents/swarm` | Agents | Swarm config | Swarm surface | Structural concept queued (P6) | Defer structural concepts | P6 queue / P8 | NOT PROVEN | — |
| `/agents/[id]` | Agents | Agent overview | Agent detail | Detail chrome monoculture | Interaction redesign gated | P8 | NOT PROVEN | — |
| `/agents/[id]/chat` | Agents | Chat with agent | Agent chat | Dual chrome vs `/ai` | Shared-system update + WM | P8 after G-STRUCT | NOT PROVEN | — |
| `/agents/[id]/capabilities` | Agents | Capabilities | Caps panel | Progressive disclosure weak | Shared-system update | P8 | NOT PROVEN | — |
| `/agents/[id]/knowledge` | Agents | Agent knowledge | Knowledge tab | Card / empty density | Composition improvement | P8 | NOT PROVEN | — |
| `/agents/[id]/memory` | Agents | Agent memory | Memory tab | Honesty / PII gates | Shared-system update | P8 | NOT PROVEN | — |
| `/training` | Agents | Train | Training surface | Header monoculture | Interaction redesign gated | P8 | NOT PROVEN | — |
| `/multi-agent-run` | Agents | Run multi-agent | Multi-agent run | Structural redesign gated | Interaction redesign gated | P8 | NOT PROVEN | — |
| `/workflows` | Workflows | Browse workflows | Workflow list | List density | Composition improvement | P8 | NOT PROVEN | — |
| `/workflows/new` | Workflows | Create workflow | Create entry | Entry → builder handoff | Shared-system update | P8 | NOT PROVEN | — |
| `/workflows/[id]` | Workflows | Workflow summary | Detail | Empty / run linkage | Composition improvement | P8 | NOT PROVEN | — |
| `/workflows/[id]/builder` | Workflows | Build / edit | Custom builder + persistence | Custom canvas; RF preferred §17 | Harness RF done; production cutover gated | P6 harness ✅ / P8 gated | Harness only | `?s=workflow-rf` |
| `/workflows/[id]/schedules` | Workflows | Schedule workflow | Nested schedules | Nested chrome | Shared-system update | P8 | NOT PROVEN | — |
| `/workflows/failure-predictions` | Workflows | Failure insight | Failure predictions | Expert density | Composition improvement | P8 | NOT PROVEN | — |
| `/runs` | Workflows | Browse runs | Runs list | TRACE grammar continuity | Shared-system update | P8 | NOT PROVEN | — |
| `/runs/[id]` | Workflows | Inspect run | Run detail | Stage-pinned story incomplete | Shared-system update | P8 | NOT PROVEN | — |
| `/schedules` | Workflows | Manage schedules | Schedules list | Form density | Shared-system update | P8 | NOT PROVEN | — |
| `/intelligence` | Intelligence | Insight→expert | Living map + RF relationships | Matrix primacy; empty density | Composition + Field primacy | P6 harness partial / P8 gated | Harness only | `?s=intelligence` |
| `/intelligence/performance` | Intelligence | Perf lens | Performance view | Nested lens chrome | Composition improvement | P8 | NOT PROVEN | — |
| `/intelligence/learning` | Intelligence | Learning | Learning view | Empty density | Composition improvement | P8 | NOT PROVEN | — |
| `/intelligence/memory` | Intelligence | Memory | Memory view | Honesty / gate caveats | Shared-system update | P8 | NOT PROVEN | — |
| `/intelligence/predictive` | Intelligence | Predictive | Predictive view | Expert density | Composition improvement | P8 | NOT PROVEN | — |
| `/intelligence/reports` | Intelligence | Reports | Reports view | Card / export chrome | Composition improvement | P8 | NOT PROVEN | — |
| `/intelligence/agents` | Intelligence | Agents in KG | Intelligence agents list | Overlap vs `/agents` | Consolidate / Composition | P8 | NOT PROVEN | — |
| `/intelligence/agents/[id]` | Intelligence | Agent in map | Nested agent detail | Dual detail paths | Consolidate | P8 | NOT PROVEN | — |
| `/intelligence/model-studio` | Models | Configure models | Model Studio | Often overlooked in redesigns | Shared-system + progressive disclosure | P6 harness ✅ / P8 | Harness only | `?s=model-studio` |
| `/intelligence/models` | Models | Model catalogue | Models under Intelligence | Family split vs `/models*` | Shared-system update | P8 | NOT PROVEN | — |
| `/intelligence/models/[name]` | Models | Named model | Dynamic model detail | Progressive disclosure | Shared-system update | P8 | NOT PROVEN | — |
| `/models` | Models | Model list | Top-level models | Split surface vs Intelligence | Shared-system update | P8 | NOT PROVEN | — |
| `/models/[id]` | Models | Model by id | Dynamic model | Detail chrome | Shared-system update | P8 | NOT PROVEN | — |
| `/models/built-in` | Models | Built-in models | Built-in catalogue | Overlooked nested path | Shared-system update | P8 | NOT PROVEN | — |
| `/models/built-in/[name]` | Models | Built-in detail | Named built-in | Progressive disclosure | Shared-system update | P8 | NOT PROVEN | — |
| `/connectors` | Knowledge / integrations | Connect systems | Connector list | Card catalogue risk; header clutter | Composition improvement | P8 | NOT PROVEN | — |
| `/connectors/[id]` | Knowledge / integrations | Connector detail | Inspector | Header clutter | Composition improvement | P8 | NOT PROVEN | — |
| `/sources` | Knowledge / integrations | Manage sources | Source list | Card catalogue risk | Composition improvement | P8 | NOT PROVEN | — |
| `/sources/[id]` | Knowledge / integrations | Source detail | Source inspector | Nested chrome | Composition improvement | P8 | NOT PROVEN | — |
| `/sources/[id]/agents` | Knowledge / integrations | Source↔agents | Nested agents tab | Dual navigation | Shared-system update | P8 | NOT PROVEN | — |
| `/integrations` `/integrations/new` `/integrations/[id]` | Knowledge / integrations | Integrations CRUD | Parallel to connectors | Possible duplicate family | Consolidate vs connectors | P8 | NOT PROVEN | — |
| `/marketplace/assets` | Business | Discover packs | Asset catalogue | App-store card risk; no invented prices | Composition improvement | P8 | NOT PROVEN | — |
| `/marketplace/assets/[slug]` | Business | Pack detail | Dynamic asset | Install honesty; no scaffold prices | Composition improvement | P8 | NOT PROVEN | — |
| `/marketplace/installed` | Business | Manage installed | Installed list | Ops list density | Composition improvement | P8 | NOT PROVEN | — |
| `/marketplace/connectors` | Business | Marketplace connectors | Connector packs | Card catalogue risk | Composition improvement | P8 | NOT PROVEN | — |
| `/marketplace/saved` `/marketplace/private` `/marketplace/sandbox` | Business | Saved / private / sandbox | Nested marketplace modes | Secondary surfaces undercounted | Composition improvement | P8 | NOT PROVEN | — |
| `/marketplace/submit` `/marketplace/role-packs` | Business | Submit / role packs | Submit + packs | Form / card chrome | Composition improvement | P8 | NOT PROVEN | — |
| `/marketplace/billing` | Business | Marketplace billing | Billing surface | **No invented prices** | Shared-system update | P8 | NOT PROVEN | — |
| `/marketplace/analytics` `/marketplace/analytics/roi` | Business | Marketplace analytics | Analytics nested | ROI claim risk if scaffolded | Composition improvement | P8 | NOT PROVEN | — |
| `/marketplace/publisher` `/marketplace/publisher/analytics` | Business | Publisher | Publisher + analytics | Admin density | Shared-system update | P8 | NOT PROVEN | — |
| `/marketplace/admin` `/marketplace/org` `/marketplace/org/assets/new` `/marketplace/org-admin` `/marketplace/platform-admin` | Business/admin | Org / platform admin | Admin trees | Dense admin chrome | Shared-system update | P8 | NOT PROVEN | — |
| `/settings` | Business/admin | Admin hub | Settings root | Density / progressive forms | Shared-system update | P8 | NOT PROVEN | — |
| `/settings/profile` | Business/admin | Profile | Profile form | Form density | Shared-system update | P8 | NOT PROVEN | — |
| `/settings/organizations` | Business/admin | Orgs | Org settings | Progressive disclosure | Shared-system update | P8 | NOT PROVEN | — |
| `/settings/team/permissions` | Business/admin | Permissions | Nested permissions | Dense RBAC UI | Shared-system update | P8 | NOT PROVEN | — |
| `/settings/approvals` | Business/admin | Approval policy | Settings approvals | Dual with `/approvals` queue | Shared-system update | P8 | NOT PROVEN | — |
| `/settings/billing` `/settings/billing/checkout` `/settings/billing-usage` | Business/admin | Billing | Billing + checkout + usage | **No invented prices/claims** | Shared-system update | P8 | NOT PROVEN | — |
| `/settings/enterprise` `/settings/federation` | Business/admin | Enterprise / federation | Nested enterprise | Expert density | Shared-system update | P8 | NOT PROVEN | — |
| `/dev/ai-workspace-preview` | Harness | Design review | Prototype venue | N/A | Retain harness | P0–7 | Harness | Branch only |
| Harness `?s=window-manager` | Harness | WM modes | Docked + modes | Selection A | Retain harness | P6 | Harness only | Preview scenes |
| Harness `?s=ai-workspace` | Harness | AI composition | Conversation/work slots | Selection B | Retain harness | P6 | Harness only | Preview scenes |
| Harness `?s=page-intro` | Harness | Hierarchy variants | Intro concepts | Selection E / G-STRUCT | Retain harness | P6 | Harness only | Preview scenes |

**Route row count (this matrix):** 79 (product nested/dynamic + retained core/harness rows; marketing/`e2e`/`api` excluded).

## Legend

- **Design disposition:** Retain · Shared-system update · Composition improvement · Interaction redesign · Consolidate · Defer  
- **Test / visual:** `NOT PROVEN` = no authenticated customer-journey evidence. `Harness only` = isolated `/dev/ai-workspace-preview` prototype — **not** production proof.  
- **Completion evidence:** Requires authenticated journey + audit/visual proof per §46 — pytest alone insufficient for customer UX claims.

## Scan basis (2026-09-23)

`apps/web/app/**/page.tsx` excluding `api/` and marketing group; `e2e/*` listed in inventory but not expanded here. Nested expansions prioritized for: intelligence, workflows (+ runs/schedules), agents, marketplace, connectors, sources, settings, model-studio/models, assignments, goals, home/lite, approvals/activity.

## Still thin / next expansions

- Desktop / extension / onboarding / platform CS workspace / environments / systems / tasks / outcomes / deliverables / search / welcome  
- Attach reference-patterns column from `05-reference-selection-matrix.md` per family when Phase 8 planning starts

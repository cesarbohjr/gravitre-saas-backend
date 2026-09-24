# 15 — Coverage matrix (§43)

**Status:** Living gate — not complete until every route has disposition + evidence.  
**Source inventories:** `02-route-interaction-inventory.md` · master §§28–30.  
**Rule:** No broad redesign complete while important routes remain unaccounted for.

| Route / family | Experience family | User job | Existing capability | Current defects (summary) | Design disposition | Impl phase | Test / visual | Completion evidence |
|----------------|-------------------|----------|---------------------|---------------------------|--------------------|------------|---------------|---------------------|
| `/ai` + float shells | Core / Ask | Intent + work | Custom AI runtime | Dual Meson/Ask chrome; docked missing | Shared-system update + WM | P8 after G-STRUCT | NOT PROVEN | — |
| `/activity` `/approvals` `/notifications` | Core | Observe / approve | TRACE + queue | Composition density | Shared-system update | P8 | NOT PROVEN | — |
| `/assignments*` `/goals*` | Core | Own outcomes | Lists + create | Confidence display bugs; empty goals | Composition improvement | Defect now / P8 | NOT PROVEN | — |
| `/home` `/lite*` | Core | Orient | Home / lite | KPI card risk | Composition improvement | P8 | NOT PROVEN | — |
| `/agents*` `/training` `/multi-agent-run` | Agents | Configure / run | Roster + detail | Header monoculture | Interaction redesign gated | P8 | NOT PROVEN | — |
| `/workflows*` builder `/runs*` `/schedules` | Workflows | Build / run | Custom builder + persistence | Custom canvas; RF preferred §17 | Harness RF done; production cutover gated | P6 harness ✅ / P8 gated | Harness only | `?s=workflow-rf` |
| `/intelligence*` Field/Matrix/KG/Rel | Intelligence | Insight→expert | Living map + RF relationships | Matrix primacy; empty density | Composition + Field primacy | P6 harness partial / P8 gated | NOT PROVEN | `?s=intelligence` |
| `/intelligence/model-studio` `/models*` | Models | Configure models | Model Studio routes exist | Often overlooked in redesigns | Shared-system + progressive disclosure | P6 harness next / P8 | NOT PROVEN | — |
| `/connectors*` `/sources*` | Knowledge / integrations | Connect systems | List + inspector | Card catalogue risk; header clutter | Composition improvement | P8 | NOT PROVEN | — |
| `/marketplace/**` | Business | Discover packs | Install flows | App-store card risk; no invented prices | Composition improvement | P8 | NOT PROVEN | — |
| `/settings*` org/billing | Business/admin | Admin | Settings trees | Density / progressive forms | Shared-system update | P8 | NOT PROVEN | — |
| `/dev/ai-workspace-preview` | Harness | Design review | Prototype venue | N/A | Retain harness | P0–7 | Harness | Branch only |

## Legend

- **Design disposition:** Retain · Shared-system update · Composition improvement · Interaction redesign · Consolidate · Defer  
- **Completion evidence:** Requires authenticated journey + audit/visual proof per §46 — pytest alone insufficient for customer UX claims.

## Next matrix expansions

Expand nested dynamic routes (`[id]` detail children) from `app/` walk; attach reference patterns column from `05-reference-selection-matrix.md` per family.

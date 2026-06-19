# Unified Marketplace UI — v0 Handoff (MKT-6.1)

Paste into [v0.dev](https://v0.dev) for further visual polish. **Production baseline** ships at `apps/web/app/marketplace/assets/page.tsx` with staggered motion, detail drawer, install stepper, connector readiness rings, and Next.js proxies under `apps/web/app/api/marketplace/assets/*`.

Stack: Next.js App Router, React 19, TypeScript, Tailwind v4, shadcn/ui, SWR, Framer Motion. Match existing Gravitre marketplace visuals (`apps/web/app/marketplace/role-packs/page.tsx` motion patterns before redirect).

---

## API contract (production)

All routes require auth + org context. Proxies: `apps/web/app/api/marketplace/**` → FastAPI.

| Method | Path | Response shape |
|--------|------|----------------|
| GET | `/api/marketplace/assets?assetType=&search=&limit=` | `{ assets[], total, limit, offset }` |
| GET | `/api/marketplace/assets/{slugOrId}` | `{ asset }` with `config`, `connectorChecklist`, `blockers[]`, `canInstall` |
| GET | `/api/marketplace/assets/{id}/install-check` | `{ canInstall, blockers[], connectorChecklist[] }` |
| POST | `/api/marketplace/assets/{id}/install` | `{ installed, entities, connectorChecklist }` — **409** when connectors missing |
| POST | `/api/marketplace/assets/{id}/clone` | `{ cloned, asset: { status: "draft", visibility: "private" } }` |
| GET | `/api/marketplace/installs` | `{ installs[] }` each with `deepLinks[{ path, entityType, label }]` |
| GET | `/api/marketplace/categories` | `{ categories[], departments[], assetTypes[], totalAssets }` |

### Connector blocker shape (required for install UX)

```json
{
  "canInstall": false,
  "blockers": [
    {
      "connector": "hubspot",
      "reason": "HubSpot CRM is not connected",
      "action_url": "/connectors?type=hubspot"
    }
  ],
  "connectorChecklist": [
    {
      "connectorType": "hubspot",
      "label": "HubSpot CRM",
      "required": true,
      "connected": false,
      "connectPath": "/connectors?type=hubspot",
      "action_url": "/connectors?type=hubspot",
      "ready": false
    }
  ]
}
```

Use `action_url` (fallback `connectPath`) for CTA links to `/connectors`.

### Asset summary fields

Each card in `assets[]` includes: `id`, `slug`, `title`, `description`, `assetType` (`ai_agent` | `workflow` | `knowledge_pack` | `department_pack`), `department`, `tags`, `pricingType`, `installed`, `canInstall`, `connectorsReady`, `requiredConnectorsConnected`, `requiredConnectorsTotal`, `connectorChecklist`, `installCount`, `averageRating`.

---

## v0 prompt

```
Enhance Gravitre unified marketplace at apps/web/app/marketplace/assets/page.tsx.

READ the existing page and apps/web/lib/api.ts marketplaceApi.listAssets/installAsset/cloneAsset first.
Do NOT duplicate /marketplace/role-packs (redirects here).

Design a premium catalog:

1. HERO + FILTERS
   - Tabs: All | Agents | Workflows | Knowledge | Department packs (maps to assetType query param)
   - Search input debounced → search query param
   - Optional sidebar facet counts from GET /api/marketplace/categories

2. ASSET CARDS
   - Type icon, title, department, tags, install count / rating if present
   - Connector readiness ring (requiredConnectorsConnected / requiredConnectorsTotal)
   - Installed badge when asset.installed

3. CONNECTOR CHECKLIST PANEL (inline on card or expandable)
   - Render connectorChecklist items
   - Blocked required connectors → primary CTA linking to item.action_url
   - Match severity: green connected, amber optional missing, red required missing

4. ACTIONS (admin install, all users clone)
   - Install button disabled when !canInstall; tooltip lists blockers with links
   - On 409 install error, toast with "Connect apps" linking to first blocker.action_url
   - Clone → toast "Draft copy created" (private org template)

5. DETAIL DRAWER (optional polish)
   - GET /api/marketplace/assets/{slug} for full config preview + packItems on department_pack
   - Show blockers[] prominently above Install

6. EMPTY / LOADING
   - Skeleton grid while SWR loading
   - Empty state when totalAssets === 0 with hint to run seed script

Motion: staggered card entrance like legacy role-packs page; reduced-motion safe.
Theme: navy enterprise (#0B0F14), Geist, existing AppShell + GridPattern.
Use marketplaceApi only — no mock data.
```

---

## Client helpers

```typescript
import { marketplaceApi } from "@/lib/api"

const { assets } = await marketplaceApi.listAssets({ assetType: "department_pack" })
await marketplaceApi.installAsset("marketing-operations-pack") // admin
await marketplaceApi.cloneAsset("marketing-analyst")
```

Types: `apps/web/types/api.ts` — `MarketplaceAssetSummary`, `MarketplaceConnectorChecklistItem`, `MarketplaceInstallBlocker`.

---

## Related

- Seed catalog: `python backend/scripts/seed_marketplace.py`
- Backend router: `backend/app/routers/marketplace.py`
- Legacy packs doc: `docs/integration/agent-role-marketplace.md` (superseded for browse by unified assets API)
- Tier 6 roadmap: `docs/integration/TIER6_PLANNING.md` (Lane B/C v2/v3)

---

## Roadmap — v2 / v3 (unified catalog)

Aligned with `POST_TIER5_BACKLOG.md` and Linear STA-233–239.

### v2 (next)

| Item | Linear | Scope |
|------|--------|--------|
| Facet filters | STA-233 | Clickable category + department chips; URL-synced `?assetType=&department=` |
| Install blocker UX | MKT-6.1 | Blocker list in drawer, 409 toast with connector deep links (see sections 3–5 above) |
| CS suggestion links | — | Department pack suggestions deep-link to filtered catalog, not legacy `/role-packs` |

### v3 (later)

| Item | Linear | Scope |
|------|--------|--------|
| Asset slug route | STA-234 | `/marketplace/assets/[slug]` shareable URLs + OG metadata |
| Reviews & saves | STA-236 | Community signals on cards; saved assets list |
| E2E prod smoke | STA-239 | CI workflow against staging/prod API with GitHub secrets |
| Analytics polish | STA-235 | Publisher dashboard charts tied to unified asset IDs |

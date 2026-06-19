# Tier 6 planning (active)

Tier 5 (STA-100–124) and marketplace M1–M5 are **code-complete**. Production verification is **green** except Clio browser OAuth (C.6).

**Current focus:** **Lane B P1 UI** — workflow pre-run simulate/scan, federation B2B tabs; Lane C skipped audit documented.

---

## Version map

| Version | Scope | Status |
|---------|--------|--------|
| **v0** | CS workspace rollups, recommendation apply API, mobile approvals baseline, agent swarm UI | ✅ Shipped |
| **v1** | Org drill-down, snapshot backfill, assign/snooze queue, Meson/GoalService apply | ✅ Shipped |
| **v2** | Escalate + alert inbox, apply result UX, approvals SLA, marketplace facet UX | ✅ Shipped |
| **v3** | PWA push, partner analytics, slug/reviews/CI smoke, enterprise polish | Backlog |

---

## Priority lanes

| Lane | Scope | v2 | v3 |
|------|-------|----|----|
| **A — Tier 6 product** | CS workspace, recommendation apply, mobile approvals, partner analytics | Escalate, alert inbox, apply toasts, SLA countdown | PWA push, partner revenue dashboards |
| **B — P1 UI gaps** | APIs exist; thin/missing surfaces | STA-233 facet filters on unified catalog | STA-234 slug route, STA-236 reviews |
| **C — Marketplace M1** | Audit leftovers | Install blocker UX polish (`V0_MARKETPLACE_UNIFIED_PROMPT.md`) | STA-239 E2E prod smoke in CI |
| **D — Enterprise polish** | White-label + workforce | Branding live preview panel | DNS stepper UX, workforce KPI sparklines |

---

## A — Tier 6 product backlog

### T6-1 — Multi-tenant CS workspace

| Version | Deliverable | Status |
|---------|-------------|--------|
| v0 | `GET /api/platform/cs-workspace/tenants`, `/platform/cs-workspace` UI | ✅ |
| v1 | Org drill-down (`x-org-id`), snapshot backfill, assign/snooze (`platform_cs_tenant_queue`) | ✅ |
| **v2** | **Escalate** tenant (`POST …/tenants/{id}/escalate` → Slack/email webhook); **cross-org alert inbox** (open failure alerts + suggestions per tenant); **scheduled backfill** (nightly worker for orgs without snapshot) | ☐ |
| **v3** | Cross-org health **trend sparklines**; CSV export for CS standups; Linear epic **T6-CS-Workspace** closed | ☐ |

**v2 API sketch:**

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/platform/cs-workspace/tenants/{orgId}/escalate` | Notify on-call with tenant context + deep link |
| GET | `/api/platform/cs-workspace/alerts` | Paginated open failure alerts across orgs |
| POST | `/api/platform/cs-workspace/snapshots/backfill` (cron) | Internal/worker trigger (reuse v1 service) |

---

### T6-2 — Workflow recommendation apply

| Version | Deliverable | Status |
|---------|-------------|--------|
| v0 | `POST /api/enterprise/integration-suggestions/{id}/apply`, CS dashboard **Apply** | ✅ |
| v1 | Meson/GoalService workflow draft + invoke_tool fallback | ✅ |
| **v2** | **Apply result UX** — toast/panel with install entities, workflow node count, blocker links; open builder with **suggestion evidence** sidebar | ☐ |
| **v3** | Re-generate applied workflow via Meson with connector-aware steps; pack install progress stepper; Linear epic **T6-Recommendation-Apply** | ☐ |

---

### T6-3 — Partner revenue analytics

| Version | Deliverable | Status |
|---------|-------------|--------|
| v0 | `/marketplace/publisher/analytics` (partial) | ✅ baseline |
| **v2** | Gross/net **time-series by asset** (30/90d); platform-admin rollup card | ☐ |
| **v3** | Payout reconciliation export; publisher cohort filters; connect to M5 billing sync | ☐ |

---

### T6-4 — Mobile operator approvals

| Version | Deliverable | Status |
|---------|-------------|--------|
| v0 | Mobile queue/detail split, sticky actions, `/approvals?id=` deep links | ✅ |
| **v2** | **SLA countdown** on cards (p95 approval latency from STA-124 / run metadata); optional swipe approve/reject | ☐ |
| **v3** | **PWA + web push** for pending approvals; native shell out of scope unless requested | ☐ |

---

## B — POST_TIER5 P1 UI gaps

| Item | v1 | v2 | v3 |
|------|----|----|-----|
| Agent swarm | `/agents/swarm` | Run detail polish (aggregate UX) | Swarm templates |
| Federation | `/settings/federation` handoffs | **Grants + delegated tasks + create dialogs** ✅ | Partner invite email preview |
| Digital twin + risk scan | Builder intelligence drawer | **Workflow detail pre-run panel** ✅ | Risk → fix suggestions |
| Role packs → unified catalog | Unified catalog + facets | — | **STA-234** slug polish |
| Integration apply | CS dashboard Apply + result sheet | — | — |
| Clio OAuth (C.6) | — | Browser smoke checklist | Production sign-off |

Design reference: `docs/design/V0_MARKETPLACE_UNIFIED_PROMPT.md`.

---

## C — Marketplace audit (M1 leftovers)

Skipped items: **`docs/integration/MARKETPLACE_AUDIT_SKIPPED.md`** (still open in Linear for tracking).

| Linear | Item | Status |
|--------|------|--------|
| STA-233 | Facet filters | ✅ Shipped |
| STA-234 | Asset slug route | ✅ Route exists |
| STA-236 | Reviews/saves | Skipped → v3 |
| STA-239 | E2E prod smoke | Skipped → v3 |
| STA-229 | Catalog ≥50 | ✅ prod `total=51` |

IDs: `docs/integration/marketplace-audit-linear-ids.json`.

---

## D — Enterprise admin polish (v3)

Per `docs/design/ENTERPRISE_UI_V0_PROMPT.md` and `ENTERPRISE_UI_V0_PROMPT.md`:

- Premium Enterprise sub-nav layout
- Branding **live preview** split panel (v2)
- DNS verification **stepper** with copy-to-clipboard (v3)
- Workforce KPI **sparklines** when time-series API exists (v3)

---

## Smoke commands (production)

```bash
npm run smoke:tier5
npm run smoke:tier5-manual
npm run smoke:post-tier5
npm run smoke:ai-production:report
npm run smoke:marketplace-production
npm run smoke:marketplace-stripe
```

Reports: `docs/delivery/smoke-*-latest.json`

---

## Linear creation checklist

### v2 (create now)

1. **T6-CS-Workspace v2** — escalate + alert inbox + scheduled backfill
2. **T6-Recommendation-Apply v2** — apply result UX + builder evidence panel
3. **T6-Mobile-Approvals v2** — SLA countdown (+ optional swipe)
4. **STA-233** — marketplace facet filters (unified catalog)

### v3 (plan next)

5. **T6-Partner-Analytics** — time-series + payout export
6. **T6-Mobile-Approvals v3** — PWA + web push
7. **STA-234**, **STA-236**, **STA-239**
8. Close **STA-229** if not already closed in Linear

---

## Shipped reference (v0 + v1)

| API | UI |
|-----|-----|
| `GET /api/platform/cs-workspace/tenants` | `/platform/cs-workspace` |
| `POST /api/platform/cs-workspace/snapshots/backfill` | Backfill button |
| `POST …/tenants/{id}/assign`, `…/snooze` | Assign / Snooze on tenant rows |
| Platform org view | `enterPlatformOrgView` → `/settings/enterprise?tab=cs` |
| `POST /api/enterprise/integration-suggestions/{id}/apply` | CS dashboard **Apply** |
| `/approvals` mobile layout | Deep links, sticky bar |
| `/agents/swarm` | Agent swarm runs |

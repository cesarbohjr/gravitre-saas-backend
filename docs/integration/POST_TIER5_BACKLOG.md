# Post–Tier 5 backlog

Tier 5 (STA-100–STA-124) is **code-complete**. This doc tracks production hardening, UI wiring, and Tier 6 product work.

**Current focus:** **Tier 6 v2** — see version map in **`docs/integration/TIER6_PLANNING.md`**.

---

## Version map (Tier 6)

| Version | Shipped | Next up |
|---------|---------|---------|
| **v0** | CS workspace rollups, apply API, mobile approvals, agent swarm UI | — |
| **v1** | Org drill-down, snapshot backfill, assign/snooze, Meson apply | — |
| **v2** | — | Escalate, alert inbox, apply UX, approvals SLA, marketplace facets (STA-233) |
| **v3** | — | PWA push, partner analytics, slug/reviews/CI (STA-234/236/239), enterprise polish |

---

## Lane A — Tier 6 product

| Epic | v0 | v1 | v2 | v3 |
|------|----|----|-----|-----|
| **T6-1 CS workspace** | Tenant rollups + UI | Drill-down, backfill, assign/snooze | Escalate, alert inbox, cron backfill | Trend sparklines, CSV export |
| **T6-2 Recommendation apply** | Apply API + button | GoalService/Meson draft | Apply result panel + builder evidence | Meson re-gen, install stepper |
| **T6-3 Partner analytics** | Publisher page (partial) | — | Time-series by asset | Payout reconciliation export |
| **T6-4 Mobile approvals** | Mobile layout + deep links | — | SLA countdown, swipe (optional) | PWA + web push |

### v1 shipped (reference)

| API | UI |
|-----|-----|
| `GET /api/platform/cs-workspace/tenants` | `/platform/cs-workspace` |
| `POST /api/platform/cs-workspace/snapshots/backfill` | Backfill snapshots button |
| `POST …/tenants/{id}/assign`, `…/snooze` | Assign / Snooze controls |
| Platform org context | View CS dashboard → `/settings/enterprise?tab=cs` |
| `POST …/integration-suggestions/{id}/apply` | CS dashboard **Apply** (Meson draft) |

---

## Lane B — P1 UI gaps

| Item | Status | v2 | v3 |
|------|--------|-----|-----|
| Agent swarm | ✅ `/agents/swarm` | Detail polish | — |
| Federation | ✅ `/settings/federation` | — | — |
| Digital twin + risk scan | ✅ Builder drawer | Workflow detail pre-run panel | — |
| Integration apply | ✅ | Result UX (T6-2 v2) | — |
| Role packs → catalog | ⚠️ Redirect only | **STA-233** facets | **STA-234** slug route |
| Clio OAuth (C.6) | ⚠️ Browser required | Smoke checklist | Prod sign-off |

Design: `docs/design/V0_MARKETPLACE_UNIFIED_PROMPT.md`.

---

## Lane C — Marketplace M1 (v2 / v3)

| Item | v2 | v3 |
|------|-----|-----|
| STA-233 facet filters | Unified catalog filter bar | — |
| STA-234 asset slug route | — | Shareable `/marketplace/assets/[slug]` |
| STA-236 reviews/saves | — | Asset community signals |
| STA-239 E2E smoke | GitHub secrets setup | Scheduled prod/staging smoke |
| Install blocker UX | Per `V0_MARKETPLACE_UNIFIED_PROMPT.md` | — |

---

## P0 — Ship & verify (done)

| Item | Status |
|------|--------|
| CS dashboard UI | ✅ |
| `smoke:post-tier5`, `smoke:tier5-manual`, `smoke:ai-production:report` | ✅ |
| `smoke:marketplace-production` (51 assets) | ✅ |
| Agent swarm UI | ✅ |
| Tier 6 v1 (backfill, queue, drill-down, Meson apply) | ✅ |

---

## P2 — Enterprise admin polish (v3)

- Branding live preview (v2)
- DNS verification stepper (v3)
- Workforce KPI sparklines (v3)
- Premium Enterprise sub-nav

See `docs/design/ENTERPRISE_UI_V0_PROMPT.md`.

---

## Smoke commands

```bash
npm run smoke:tier5
npm run smoke:tier5-manual
npm run smoke:post-tier5
npm run smoke:marketplace-production
npm run smoke:marketplace-stripe:fulfill   # needs STRIPE_SECRET_KEY locally
```

Requires `backend/.env.operator.local` with Supabase JWT + service role.

---

## Related docs

- `TIER6_PLANNING.md` — full v2/v3 breakdown + Linear checklist
- `marketplace-audit-linear-ids.json` — STA-233–239
- `V0_MARKETPLACE_UNIFIED_PROMPT.md` — unified catalog UX v2
- `integration-health-score.md` — STA-124
- `auto-suggest-connectors-workflows.md` — STA-123 + apply
- `predictive-workflow-failure.md` — STA-122

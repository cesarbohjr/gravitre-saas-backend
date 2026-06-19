# Post–Tier 5 backlog

Tier 5 (STA-100–STA-124) is **code-complete**. This doc tracks production hardening, UI wiring, and Tier 6 product work.

**Current focus:** **Lane B P1 UI** — workflow pre-run intelligence, federation B2B tabs, marketplace skipped audit docs.

---

## Version map (Tier 6)

| Version | Shipped | Next up |
|---------|---------|---------|
| **v0** | CS workspace rollups, apply API, mobile approvals, agent swarm UI | — |
| **v1** | Org drill-down, snapshot backfill, assign/snooze, Meson apply | — |
| **v2** | Escalate, alert inbox, apply UX, approvals SLA, marketplace facets | ✅ Shipped |
| **v3** | PWA push, partner analytics, slug/reviews/CI, enterprise polish | Backlog |

---

## Lane A — Tier 6 product

See **`docs/integration/TIER6_PLANNING.md`** for CS workspace, apply, approvals, partner analytics.

---

## Lane B — P1 UI gaps

| Item | Status | Notes |
|------|--------|-------|
| Agent swarm | ✅ `/agents/swarm` | — |
| Federation | ✅ `/settings/federation` | Handoffs + **connector grants** + **delegated tasks** tabs |
| Digital twin + failure scan | ✅ | Builder drawer + **`/workflows/[id]` pre-run panel** (Simulate + scan) |
| Integration apply | ✅ | Apply result sheet (T6-2 v2) |
| Role packs → catalog | ✅ | Unified catalog + facet filters |
| Clio OAuth (C.6) | ⚠️ Browser required | Smoke checklist |

Design: `docs/design/V0_MARKETPLACE_UNIFIED_PROMPT.md`.

---

## Lane C — Marketplace M1 (skipped in Linear)

Audit items remain in Linear but are **documented as skipped/deferred** — see **`docs/integration/MARKETPLACE_AUDIT_SKIPPED.md`**.

| Item | Status |
|------|--------|
| STA-233 facet filters | ✅ Shipped |
| STA-234 slug route | ✅ Route exists; OG polish v3 |
| STA-236 reviews/saves | Skipped → v3 |
| STA-239 E2E smoke | Skipped → v3 |
| STA-229 catalog ≥50 | ✅ prod `total=51` — close in Linear |

---

## P0 — Ship & verify (done)

CS workspace, agent swarm, Tier 6 v2, nightly backfill GitHub Action — see git history and `TIER6_PLANNING.md`.

---

## Smoke commands

```bash
npm run smoke:tier5
npm run smoke:tier5-manual
npm run smoke:post-tier5
npm run smoke:marketplace-production
```

Requires `backend/.env.operator.local` with Supabase JWT + service role.

---

## Related docs

- `TIER6_PLANNING.md`
- `MARKETPLACE_AUDIT_SKIPPED.md`
- `marketplace-audit-linear-ids.json`
- `predictive-workflow-failure.md` — STA-122

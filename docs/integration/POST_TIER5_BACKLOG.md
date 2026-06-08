# Post–Tier 5 backlog

Tier 5 (STA-100–STA-124) is **code-complete**. This doc tracks production hardening, UI wiring, and the next product slice.

**Current focus:** P0 production smoke + CS dashboard + department role packs UI.

---

## P0 — Ship & verify (now)

| Item | Status | Notes |
|------|--------|-------|
| CS dashboard UI (`/settings/enterprise?tab=cs`) | ✅ | Health score, suggestions, failure alerts |
| `npm run smoke:post-tier5` | ✅ | Platform intelligence + role packs API smoke |
| Extend `TIER5_PRODUCTION_SMOKE.md` (Epics D–F) | ✅ | Federation, workforce, intelligence |
| Commit + deploy web + API | ☐ | Railway + Vercel |

## P1 — UI gaps for shipped APIs

| Item | API | UI target |
|------|-----|-----------|
| Department role packs | `GET/POST /api/marketplace/role-packs` | `/marketplace/role-packs` |
| Workflow digital twin | `POST /api/workflows/digital-twin` | Workflow builder “Simulate” action |
| Failure prediction scan | `POST /api/workflows/{id}/failure-predictions/scan` | Workflow detail pre-run panel |
| Federation / B2B handoffs | `/api/federation/*` | Settings or partner admin page |
| Agent swarm runs | `/api/agent-swarm/*` | Operators or assignments UI |

## P2 — Enterprise admin polish

Per `docs/design/ENTERPRISE_UI_V0_PROMPT.md`:

- Premium sub-nav layout refinements
- Branding live preview panel
- DNS verification stepper UX
- Workforce KPI sparklines (when backend exposes series)

## P3 — Tier 6 candidates (planning)

Not yet in Linear. Candidates for the next epic batch:

1. **Multi-tenant CS workspace** — cross-org health rollups for Gravitre operators
2. **Workflow recommendation apply** — one-click create workflow from STA-123 suggestions
3. **Partner revenue analytics** — marketplace billing + usage dashboards
4. **Mobile operator approvals** — push-friendly approval queue

Create Linear epics when prioritizing Tier 6.

---

## Smoke commands

```bash
npm run smoke:tier5        # Vertical packs (legal, real estate) + Clio
npm run smoke:post-tier5    # Platform intelligence + role packs (STA-122–124, STA-121)
```

Requires `backend/.env.operator.local` with Supabase JWT + service role (same as Tier 5 smoke).

---

## Related docs

- `LINEAR_INTEGRATION_BACKLOG.md` — Tier 1–5 complete
- `integration-health-score.md` — STA-124
- `auto-suggest-connectors-workflows.md` — STA-123
- `predictive-workflow-failure.md` — STA-122
- `agent-role-marketplace.md` — STA-121

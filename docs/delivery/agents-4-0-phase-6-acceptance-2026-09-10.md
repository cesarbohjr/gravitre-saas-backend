# Agents 4.0 — Phase 6 acceptance checklist

**Date:** 2026-09-10  
**Scope:** Playwright goldens + desktop OS identity alignment audit  
**Exit:** Acceptance checklist (this document)

## Deploy prerequisites (Phases 1–5)

| Gate | Evidence |
|------|----------|
| Phases 1–4 on `main` | `67c43329` |
| Phase 4/5 prod READY | `dpl_FoPu9VWwp7UkQZasbjkbbAcEP8ei` (1–4), `dpl_GNzD5q6NdsfKCrcUVjtwniBSJqf1` (Phase 5 `535999d3`) |
| Production alias | https://gravitre.app |

Local pytest / tsc alone is **not** production PASS for user-facing fleet UX.

## Acceptance criteria

### Identity

- [ ] Soft Nucleo/Nodus tiles on `/agents` (no glow-orb constellation as default roster)
- [ ] Status is a corner/dot/chip — identity color does not recolor for Running/Failed
- [ ] Appearance picker copy forbids glow orbs / freeform colors

### Fleet views

- [ ] TEAM \| LIST \| GRAPH switcher (`Fleet view` group)
- [ ] TEAM: department-grouped compact cards; Train not on every card
- [ ] LIST: dense table with Agent column; filters/sort present
- [ ] GRAPH: edges only from parent / swarm / connectors; legend honest

### Inspector (Phase 5)

- [ ] Sheet + desktop panel share one inspector body
- [ ] Train lives in inspector / profile — not roster cards

### Visual goldens (this phase)

| Suite | Path | Refresh |
|-------|------|---------|
| Agents 4.0 | `e2e/visual/agents-4.spec.ts` | `pnpm test:agents-visual -- --update-snapshots` |
| Product pack agents surface | `e2e/visual/nodus-product-fidelity.spec.ts` (`agents` row) | refresh after fleet UI changes |

Commands:

```bash
PLAYWRIGHT_REUSE_SERVER=1 pnpm test:agents-visual -- --update-snapshots
PLAYWRIGHT_REUSE_SERVER=1 pnpm test:agents-visual
```

Optional marketing PNG refresh:

```bash
node scripts/capture-product-shots.mjs --only agents
```

### Desktop OS alignment

| Surface | Finding | Action |
|---------|---------|--------|
| `apps/desktop` | No `AgentIdentityAvatar` / glow-orb agent identity | **N/A** — nothing to migrate |
| Marketing desktop companion preview | Structural mock, no agent tiles | Leave |
| Web agent detail `AgentOrb` | Renamed to `AgentIdentityHero` (soft tile) | Done in Phase 6 |
| Chat transcript avatars | `GravitreChatAvatar` by design | Out of scope |

## Explicitly out of scope

- Invented collaborates/escalates edges
- Fake TRAINED badges / prices / Enable toggles
- Full Nucleo replacement of every Nodus-nav glyph
- Desktop companion chat avatar redesign (no agent identity surface today)

## Sign-off

| Item | Owner | Result |
|------|-------|--------|
| Goldens generated / committed | Engineering | Local PASS 2026-09-10 — `pnpm test:agents-visual` 12/12 on chromium-win32 |
| Prod `/agents` spot-check TEAM/LIST/GRAPH | Human | _(fill)_ |
| Acceptance | Product | _(fill)_ |

**(a)** No new customer-facing prices/claims/badges invented in Phase 6.  
**(b)** Fixture gallery + shot harness remain capture-only (`/e2e/shots/*` 404 in production).

## Nodus fleet polish (2026-09-10)

Follow-up after Phase 6 goldens:

- ConnectorsAtmosphere (10px dot grid) on TEAM / LIST / GRAPH canvas
- Sharper identity tiles (solid surfaces, no washed `/90` fades)
- GRAPH edges use connectors/tech-stack `motion.linearGradient` sweeps
- Drag agents onto department teams in TEAM, LIST, and GRAPH; persists via `PATCH /api/agents/:id` `department`

Prod spot-check after merge → Vercel READY → https://gravitre.app/agents: confirm dot grid, sharp icons, department drag, animated graph edges.

# Gravitre internal documentation

**Audience:** Gravitre team only  
**Publish:** Private docs site (`apps/internal-docs`) — not bundled in the public Vercel app

## Frontmatter (required)

```yaml
---
title: "Page title"
description: "One-line summary"
audience: internal
depth: high | mid | deep
status: draft | review | published
category: Architecture | Runbooks | Integration | Compliance
---
```

## Directory layout

| Path | Purpose |
|------|---------|
| `architecture/` | System structure, data flow (no proprietary algorithms) |
| `runbooks/` | Ops, deploy, smoke tests |
| `integration/` | Engineer-facing connector notes (migrate from `docs/integration/` over time) |
| `compliance/` | SOC2, FedRAMP gap, evidence mapping |

## Public vs internal

- **Public** customer docs live in `apps/web/content/docs/public/` (MDX, `audience: public`)
- **Internal** docs live here — never import into `apps/web` marketing routes

## Access

Deploy `apps/internal-docs` to a private URL with `INTERNAL_DOCS_PASSWORD` or SSO.

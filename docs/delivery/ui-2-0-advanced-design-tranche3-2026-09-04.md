# Advanced Design — tranche 3 STATUS surface pass (2026-09-04)

**Depends on:** pilots `0ffc63d6`, tranche 2 `2984a86c` (on `origin/main`)

## Scope

Canvas §J ops density — STATUS / CSS status tokens only. No layout or IA changes.

| Surface | Files |
|---------|--------|
| Connectors hub + detail | `connectors/page.tsx`, `connectors/[id]/page.tsx` statusConfig |
| Connector linkage / strip | `connector-linkage.tsx`, `available-connectors-strip.tsx` |
| GIBE / intelligence | `lib/intelligence/helpers.ts`, `visibility-helpers.ts` |
| Swarm badges | `swarm-status-badge.tsx` |
| Agents | `[id]/page.tsx` SystemBadge dots; chat presence; knowledge statusClasses |
| Runs | `[id]/page.tsx` progress fill |

## Explicit non-claims

- Decorative skill-bar / category filter rainbows left untouched (not status language).
- Design Mode loop and §64 full acceptance still pending Cesar visual pass.
- Voice human verify still separate.

## Customer surfaces

No new prices/claims/badges/Enable toggles. **(a)** Approved augmentation.

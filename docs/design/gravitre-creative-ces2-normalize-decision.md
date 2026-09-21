# CES 2.0 — Knowledge Fabric normalize decision

**Date:** 2026-09-20  
**Scope:** KF-A harness prototype only (does not change production Pilot 3)

## Decision

**Prototype (KF-A): Option A** — a small deterministic function shared by fixtures and display.

```ts
normalizeIllustrativeMention(raw):
  trim → collapse whitespace → lowercase → strip trailing .,:;!?
```

Implemented in `apps/web/components/marketing/creative/scenes/knowledge-fabric/normalize.ts`.

**Production Pilot 3: Option B retained** — precomputed `normalized` strings on `MENTIONS` in `storyboard.ts`. Production `EntityConvergenceField` is unchanged.

## Why A for the prototype

Cesar required that the NORMALIZE step be inspectable and that the animation must not contradict implementation. A shared function makes the transform the source of truth for both the fixture expectation and the on-screen “→ normalized” line.

## Honesty bounds

- Illustrative only — not live CRM sync
- Exact normalized match only — not fuzzy person ER
- “Sarah” / “Sarah Smith” remain separate (different normalized strings; no entity key)
- No fabricated confidence scores

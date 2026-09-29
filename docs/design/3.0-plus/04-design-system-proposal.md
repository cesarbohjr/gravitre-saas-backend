# 04 — Design-system consolidation proposal

**Authority:** Nodus + Gravitre emerald + Nucleo + existing light theme. Do not replace with generic SaaS kits.

## Keep

| Layer | Action |
|-------|--------|
| `--np-*` / `--g-*` CSS variables | Single source; document roles |
| Light product theme + Nodus dark where already defined | Retain intentional light direction |
| shadcn primitives | Thin wrappers only |
| Creative grammar (`EvidenceChip`, TracePath) | Extend into Activity / Runs / Approvals |
| MotionProvider reduced-motion | Enforce; lint ad-hoc Framer sprawl later |

## Consolidate

| Problem | Proposal |
|---------|----------|
| `GravitrePageHeader` monoculture | Intro **variants by job**: Operating (AI-first), Expert (ops), Empty, Immersive (builder/connectors) — harness first |
| Lucide/Phosphor vs Nucleo | Nucleo semantic map for nav + primary actions; Lucide only where Nucleo missing |
| Dual AI chrome (Meson vs Ask) | One intent layer; Meson becomes **workflow-local** assistant, not global peer of Ask |
| Card-first lists | Prefer table/row density for ops; cards only for interaction containers |

## Do not

- Invent customer prices, TRAINED badges, or Enable toggles as scaffold
- Purple-gradient / cream-serif / broadsheet aesthetic drifts
- Dark-mode-as-default product flip without Cesar decision
- Parallel token files that diverge from Nodus

## Prototype venue

`/dev/ai-workspace-preview` foundation + surface scenes — no production shell swap until structural gate.

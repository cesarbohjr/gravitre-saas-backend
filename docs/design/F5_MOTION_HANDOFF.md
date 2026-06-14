# F5 Motion System — Handoff (PR #38)

**Merged to `main`:** merge commit [`39cfaba`](https://github.com/cesarbohjr/gravitre-saas-backend/commit/39cfaba) (PR #38 from `v0/cesarbohorquezjr-4251-8b623736`)  
**Spec (original prompt):** [`V0_AI_INTELLIGENCE_PROMPTS.md`](V0_AI_INTELLIGENCE_PROMPTS.md) — F5 section  
**Do not re-implement** — extend using the foundation below.

---

## Foundation (shared — build on these)

### `apps/web/lib/animations.ts`

Motion tokens and reduced-motion hook:

| Export | Purpose |
|--------|---------|
| `entranceContainer` / `entranceItem` | Stagger 0.04s, opacity 0→1 + y 8→0, spring stiffness 380 / damping 32 |
| `hoverLift` | y -2px + shadow, 150ms |
| `pressScale` | scale 0.98, 80ms |
| `reducedEntranceContainer` / `reducedEntranceItem` | Static fallbacks when user prefers reduced motion |
| **`useMotionPrefs()`** | Returns `{ reduced, container, item }` — **use on any new animated surface** |

### `apps/web/components/gravitre/premium-effects.tsx`

`ParticleField`, `NeuralNetwork`, `DataStream`, `MorphingBackground` self-disable under `prefers-reduced-motion` (wrapped via `useReducedMotion`; implementations renamed to `*Impl`).

### `apps/web/app/globals.css`

Global `@media (prefers-reduced-motion: reduce)` guard collapses CSS animations, transitions, and smooth-scroll. **Any new Tailwind `animate-*` is auto-covered.**

---

## Surfaces polished (PR #38)

| # | Surface | Key files | Motion highlights |
|---|---------|-----------|-------------------|
| 1 | Meson Copilot Panel | `components/workflows/meson-copilot-panel.tsx`, builder toolbar | Spring slide-in + GlowOrb; staggered suggestions + confidence bars; collapse on dismiss/accept; StatusBeacon alerts; Fix spinner→check; `motion-safe:` attention ping on Meson toggle |
| 2 | Execution Timeline | `components/runs/execution-timeline.tsx`, `app/runs/[id]/page.tsx` | CI/CD spine; running PulseRing + DataStream; height expand/collapse; failed-step shake; parallel-batch slide-in; amber ping on approval panel |
| 3 | Assistant + Agent chat | `app/assistant/page.tsx`, `app/agents/[id]/chat/page.tsx` | Directional spring messages (user-right / assistant-left); blinking streaming cursor (`streaming` prop on `ChatMessage`); `AnimatePresence` lists; send hover/press; staggered empty suggestions |
| 4 | Conversation sidebar | `components/gravitre/assistant/conversation-sidebar.tsx` | Staggered entrance; exit-on-delete; hover nudge; shared-layout active rail `layoutId="conversation-active-rail"` |
| 5 | Agent grid | `app/agents/page.tsx` | `popLayout` AnimatePresence for filter reflow + exit |
| 6 | Meson wizard | `components/gravitre/meson-wizard.tsx` | Direction-aware step slide via `stepVariants` + `direction` state |
| 7 | Training Hub | `app/training/page.tsx` | Live shimmer overlay on `training` / `queued` job progress bars |
| 8 | Federation | `components/federation/partner-card.tsx`, `handoff-timeline.tsx` | Card entrance/hover/exit + consent-step pop; timeline stagger; pulsing pending-receiver dots |
| 9 | Lite assign | `app/lite/assign/page.tsx` | Picker stagger + shared-layout selection ring `layoutId="lite-assign-selected"` |

### Not in PR #38 (still candidates for a follow-up pass)

- Semantic search (`app/chat/page.tsx`)
- CS Command Center (`components/enterprise/cs-dashboard-tab.tsx`)
- Role pack install UI (`app/marketplace/role-packs/page.tsx`)
- Admin assign task (`app/assignments/new/page.tsx`)

---

## Gotchas

- Meson panel fetch effects use `// eslint-disable-next-line react-hooks/set-state-in-effect` — intentional external-sync loading flags.
- Pre-existing unused imports (`Check`, `Copy`) in `conversation-sidebar.tsx` — left untouched in PR #38.
- `tsc --noEmit` clean; `next build` passes after merge.

---

## Convention going forward

1. Gate infinite/looping animation behind `useMotionPrefs().reduced` or Tailwind `motion-safe:`.
2. Import stagger/hover/press from `animations.ts` — do not duplicate spring constants.
3. Prefer `premium-effects.tsx` primitives before adding new particle/ambient FX.
4. After `main` releases, run `scripts/sync-branches.ps1` so v0 import branch stays current.

---

## PR commit stack (for bisect)

```text
98ed2c7 feat(motion): F5 foundation + Meson panel & execution timeline polish
10743ea feat(motion): assistant + agent chat + conversation sidebar polish
ca61e63 feat(motion): agent grid filtering + Meson wizard direction-aware steps
1976962 feat(motion): live shimmer on active training job progress bars
573bf9d feat: integrate framer-motion animations across multiple components
0f3442c feat(motion): federation, assign-task polish + global reduced-motion guard
39cfaba Merge pull request #38
```

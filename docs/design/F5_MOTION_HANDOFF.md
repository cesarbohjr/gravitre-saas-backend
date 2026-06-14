# F5 Motion System — Handoff (PR #38 + PR #39)

**Status:** Fully shipped across the app — do not re-polish listed surfaces.

| Pass | Merge commit | PR | v0 branch |
|------|--------------|-----|-----------|
| **F5** | [`39cfaba`](https://github.com/cesarbohjr/gravitre-saas-backend/commit/39cfaba) | [#38](https://github.com/cesarbohjr/gravitre-saas-backend/pull/38) | `v0/cesarbohorquezjr-4251-8b623736` |
| **F5.1** | [`28d3f0b`](https://github.com/cesarbohjr/gravitre-saas-backend/commit/28d3f0b) | [#39](https://github.com/cesarbohjr/gravitre-saas-backend/pull/39) | `v0/cesarbohorquezjr-4251-b1471aa1` |

**Spec (original prompts):** [`V0_AI_INTELLIGENCE_PROMPTS.md`](V0_AI_INTELLIGENCE_PROMPTS.md) — F5 section

---

## Stack (reuse for any new motion work)

| Layer | Location | Notes |
|-------|----------|-------|
| Hooks / tokens | `apps/web/lib/animations.ts` | `useMotionPrefs()`, `useReducedMotion()`, `entranceContainer` / `entranceItem`, `hoverLift`, `pressScale` |
| Ambient FX | `apps/web/components/gravitre/premium-effects.tsx` | Self-disable under reduced motion (`*Impl` wrappers) |
| CSS guard | `apps/web/app/globals.css` | `@media (prefers-reduced-motion: reduce)` — covers all Tailwind `animate-*` |
| Shared layout | Framer `layoutId` | Active rails, selection rings (see surfaces below) |
| One-off loops | Tailwind `motion-safe:` | Attention pings, hover scale |

**Rule:** Any infinite animation or JS `requestAnimationFrame` loop **must** be gated behind `useMotionPrefs().reduced` or `useReducedMotion()` explicitly — the CSS guard only covers CSS animations.

---

## F5 — Surfaces polished (PR #38)

| # | Surface | Key files | Motion highlights |
|---|---------|-----------|-------------------|
| 1 | Meson Copilot Panel | `components/workflows/meson-copilot-panel.tsx`, builder toolbar | Spring slide-in + GlowOrb; staggered suggestions + confidence bars; collapse on dismiss/accept; StatusBeacon alerts; Fix spinner→check; `motion-safe:` attention ping on Meson toggle |
| 2 | Execution Timeline | `components/runs/execution-timeline.tsx`, `app/runs/[id]/page.tsx` | CI/CD spine; running PulseRing + DataStream; height expand/collapse; failed-step shake; parallel-batch slide-in; amber ping on approval panel |
| 3 | Assistant + Agent chat | `app/assistant/page.tsx`, `app/agents/[id]/chat/page.tsx` | Directional spring messages; streaming cursor on `ChatMessage`; `AnimatePresence` lists; send hover/press; staggered empty suggestions |
| 4 | Conversation sidebar | `components/gravitre/assistant/conversation-sidebar.tsx` | Staggered entrance; exit-on-delete; hover nudge; `layoutId="conversation-active-rail"` |
| 5 | Agent grid | `app/agents/page.tsx` | `popLayout` AnimatePresence for filter reflow + exit |
| 6 | Meson wizard | `components/gravitre/meson-wizard.tsx` | Direction-aware step slide via `stepVariants` + `direction` |
| 7 | Training Hub | `app/training/page.tsx` | Live shimmer on `training` / `queued` job progress bars |
| 8 | Federation | `components/federation/partner-card.tsx`, `handoff-timeline.tsx` | Card entrance/hover/exit; timeline stagger; pulsing pending-receiver dots |
| 9 | Lite assign | `app/lite/assign/page.tsx` | Picker stagger; `layoutId="lite-assign-selected"` |

---

## F5.1 — Surfaces polished (PR #39)

Closed the four surfaces deferred after PR #38.

| # | Surface | Key file | Motion highlights |
|---|---------|----------|-------------------|
| 1 | Semantic search | `app/chat/page.tsx` | Staggered sample-query chips; skeleton sweep while searching; staggered result entrance + `hoverLift` + exit (`AnimatePresence` + `layout`); animated history list with exit-on-delete; send `motion-safe:hover:scale-105` + `active:scale-90` |
| 2 | CS Command Center | `components/enterprise/cs-dashboard-tab.tsx` | `useReducedMotion` guards for JS count-up rAF loop and infinite score-ring glow (entrance/exit/hover was already present) |
| 3 | Role pack install | `app/marketplace/role-packs/page.tsx` | Animated install stepper: filling vertical connector (`scaleY`); active-step pulse ring (gated); completion checkmark pop; label color fade; reduced-motion-aware readiness ring. Fixed pre-existing `prefer-const` on install step timer |
| 4 | Admin assign wizard | `app/assignments/new/page.tsx` | Direction-aware steps (`stepVariants` + `direction`, `custom` on `AnimatePresence`); sidebar rail `layoutId="assignment-step-active"` + checkmark pop; staggered agent cards with animated training bars; selection ring `layoutId="assignment-agent-ring"`; Run-button micro-interaction; `goToStep(id)` sets direction on sidebar jumps |

---

## Gotchas

- Meson panel fetch effects: `// eslint-disable-next-line react-hooks/set-state-in-effect` — intentional external-sync loading flags.
- CS dashboard count-up: same eslint disable for reduced-motion instant-set path.
- Pre-existing unused imports (`Check`, `Copy`) in `conversation-sidebar.tsx` — left untouched in PR #38.
- F5.1 auth-gated routes validated via `tsc --noEmit` + `next build` (patterns mirror browser-verified PR #38 surfaces).
- `tsc --noEmit` clean; `next build` passes after both merges.

---

## Convention going forward

1. Gate infinite/JS rAF loops behind `useMotionPrefs().reduced` or `useReducedMotion()`.
2. Use Tailwind `motion-safe:` for CSS-only one-off loops.
3. Import stagger/hover/press from `animations.ts` — do not duplicate spring constants.
4. Prefer `premium-effects.tsx` before new particle/ambient FX.
5. After `main` releases, run `scripts/sync-branches.ps1` so v0 import branches stay current.

---

## Commit stacks (for bisect)

**PR #38**

```text
98ed2c7 feat(motion): F5 foundation + Meson panel & execution timeline polish
10743ea feat(motion): assistant + agent chat + conversation sidebar polish
ca61e63 feat(motion): agent grid filtering + Meson wizard direction-aware steps
1976962 feat(motion): live shimmer on active training job progress bars
573bf9d feat: integrate framer-motion animations across multiple components
0f3442c feat(motion): federation, assign-task polish + global reduced-motion guard
39cfaba Merge pull request #38
```

**PR #39**

```text
46f2d93 feat(motion): F5.1 pass — chat search, CS center, role pack install, assignments
28d3f0b Merge pull request #39
```

# GRAVITRE MOTION SYSTEM

**Cesar amendment:** Keep `framer-motion`. Do **not** churn ~194 files to `motion/react` without a concrete technical benefit. Productize REVEAL / FOCUS / FLOW / TRACE / PULSE / RESOLVE / TRANSFER / EXPAND / COLLAPSE / CONNECT / EXECUTE / COMPLETE. Motion must connect state (select → edge focal → inspector), not decorate. Validate `micro` / `ui` / `major` / `flow` in the design harness.

**One harness:** `/dev/ai-workspace-preview` demonstrates morph, graph focus, workflow TRACE, run TRACE, inspector REVEAL, approval RESOLVE. Not a second product runtime.

**Evidence class:** repository read 2026-09-17.

---

## What 1.0 already shipped

| Primitive | Implementation | Status |
| --- | --- | --- |
| Shared layout morph compact ↔ expanded ↔ fullscreen | `layoutId` `gravitre-ai-workspace-frame` on float + shell; `LayoutGroup id="gravitre-ai-workspace"` | Architecture **COMPLETE**; production authenticated morph **NOT PROVEN** |
| Minimize | Helper launcher; **no** shared layoutId with the window | Intentional |
| Mobile | Vaul sheet; not desktop morph | Keep |
| Enter/exit duration | `MOTION.major` 400ms; reduced-motion duration 0 | Tokens exist |

---

## Canonical tokens (already in code)

From `apps/web/lib/design-system.ts` `MOTION` and `apps/web/app/globals.css`:

| Token | Value | Use |
| --- | --- | --- |
| `--g-duration-micro` / `MOTION.micro` | 150ms / 0.15s | Hover, press |
| `MOTION.ui` / `base` | 0.25s | Standard enter/exit |
| `--g-duration-state` | 320ms | Status change |
| `MOTION.major` | 0.4s | Spatial workspace |
| `MOTION.slow` | 0.6s | Emphasis only |
| `--g-duration-flow` | 800ms | Trace / flow along a path |
| `--g-duration-ambient` | 16s | **Do not use on product ops** |
| `MOTION.stagger` | 0.04s | List insert |
| `MOTION.spring` | stiffness 400, damping 32 | Sliding indicators |
| `--g-ease-standard` | `cubic-bezier(0.4, 0, 0.2, 1)` | Default |
| `--g-ease-intelligence` | `cubic-bezier(0.22, 1, 0.36, 1)` | Inspector reveal |
| `--g-ease-signal` | `cubic-bezier(0.45, 0, 0.55, 1)` | Connection |
| `--g-ease-resolve` | `cubic-bezier(0.16, 1, 0.3, 1)` | Complete |

**2.0 rule:** new code uses these names. Do not invent 180ms / 220ms / 500ms.

`MOTION_CONCEPT` already lists FLOW · PULSE · WAVE · TRACE · RESOLVE · TRANSFER · FOCUS. **ORBIT is deprecated** for authenticated product.

---

## Vocabulary (Reset 2.0)

Every animation must answer: what changed, where it went, what is connected, what is happening, or what completed.

| Name | Answers | Duration | Typical target |
| --- | --- | --- | --- |
| REVEAL | What appeared | ui | Inspector, details |
| FOCUS | What is selected | micro + spring | Graph node, row |
| FLOW | Where work is going | flow | Workflow step, data |
| TRACE | Which path | flow | Run / relationship edge |
| PULSE | Waiting | state, 1 cycle or opacity | Approval wait, agent running |
| RESOLVE | Completed | resolve ease | Success, approval |
| TRANSFER | Object moved | major | Delegation, widget drag |
| EXPAND / COLLAPSE | Spatial state | major | AI workspace, clusters |
| CONNECT / DISCONNECT | Edge | signal ease | Graph, connectors |
| EXECUTE | Work started | micro | Run start |
| COMPLETE | Work finished | resolve | Run end |
| WAIT | Blocked | pulse, reduced-motion = static | Pending |
| FAIL | Interrupted | micro, no bounce | Error |

Forbidden: bounce, 6px lift, constant glow, decorative orbit, full-route theatrical fades.

---

## Surface rules

**AI workspace:** one object. Shared layout between compact and expanded/fullscreen. Minimize is dock, not morph. Voice uses existing `VoiceStateVisualizer` (listening / speech / thinking / speaking) — not a new orb.

**Graph:** motion on focus, selected path, cluster expand, learned edge appear. No continuous whole-graph animation.

**Workflow:** TRACE through actual nodes. Current / complete / wait / fail.

**Agents:** status line and delegation connection. No glowing avatars.

**Performance:** highlight corresponding pipeline stage on hover/focus. No decorative dashboard motion.

**Settings:** state + save confirmation only.

**Page transitions:** continuity of selected object; no app-wide route choreography.

**Data:** interpolate metrics when they update live; do not animate historical static numbers.

---

## Hover / press

Hover: background tint, border contrast, icon opacity, reveal secondary action.  
Press: 1px translate or 0.98 scale max.  
Not: new shadow on every row.

---

## Effects (restrained)

Allowed: hairline, selection ring (`--ring` brand green), faint brand tint on **selected** surface, backdrop blur **only** on true floating layers (Level 3–4).  
Do not stack glow + noise + gradient + blur.

`--g-brand-glow`, `--g-intelligence-glow`, ambient 16s, and marketing GSAP **stay off authenticated ops** unless a named visualization needs one local effect.

---

## GSAP / 3D / WebGL

| Tool | Allowed |
| --- | --- |
| GSAP | Marketing / special sequences only. Already used on marketing story. Not for table hover |
| Three.js / R3F | Not in package.json. Do not add for settings, tables, chat, lists |
| Existing WebGL | Intelligence network / core hub — keep isolated; do not expand to Settings |

---

## Performance

Prefer transform/opacity. Lazy-load graphs. Respect reduced motion by **immediate state** instead of movement.

---

## Prototype vs production

Reset 2.0 prototypes in the Cursor canvas are **spatial diagrams** (canvas SDK cannot run Framer). Production Motion remains in `apps/web` after approval.

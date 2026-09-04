# GRAVITRE UI 2.0 — Phases 2–6 depth proposals

**Date:** 2026-09-04  
**Mode:** Proposal only — no reskin implementation in this document  
**Depends on:** Phase 1 audit + sequencing gate PASS + Phase 7 tools (partial)

---

## Phase 2 — Existing Gravitre design audit

### Strengths (KEEP)

| Item | Path / evidence |
|------|-----------------|
| Emerald brand system | `apps/web/app/globals.css` — `--primary` oklch hue ~162; cool sage light / navy dark |
| Elevation + status + chart + workflow line tokens | same |
| Type / radius / motion class tokens | `lib/design-system.ts` |
| Framer motion SOTs + reduced motion | `lib/animations.ts`, `components/motion-provider.tsx` |
| Shared chat voice chrome | `voice-presentation.tsx` + `SharedChatComposerControls` + drift CI |
| PageHeader using TYPE tokens | `components/gravitre/page-header.tsx` |
| shadcn new-york primitives | `components/ui/*` (~58) |

### Weaknesses → classification

| Finding | Classification |
|---------|----------------|
| `TYPE` / `PageHeader` under-adopted (~14 importers; many hubs hand-roll titles) | **REFINE** |
| Marketing zinc island (`marketing-chrome.tsx` `bg-white text-zinc-900`) vs semantic tokens | **RESKIN** (keep marketing IA) |
| Dual timing: `design-system.MOTION` vs `animations.timing` | **REFINE** — single export |
| Lucide (~250) + Phosphor (~35) + unused Nucleo wrapper | **REPLACE** (Nucleo canonical, phased) |
| Orphan `AICommandInput` (exported, zero call sites) | **REMOVE DUPLICATE** |
| Stale `apps/web/styles/globals.css` (not imported) | **REMOVE DUPLICATE** |
| Desktop CSS island (`#16a374`, system fonts) | **SHARE** tokens later — **LAYOUT APPROVAL REQUIRED** |
| Voice hex literals in `voice-presentation.tsx` | **REFINE** → CSS vars |
| Framer in ~150 files; marketing motion density high | **REFINE** — CSS for micro; lazy marketing |
| Unused Lottie wrappers (no prod call sites found) | **REMOVE** or gate if planned |
| Docs third chrome (`docs-shell`) | **REFINE** share header primitives; **KEEP** docs IA |
| Continuous motion without local `useMotionPrefs` | **REFINE** |

### Navigation / forms / tables / charts

| Area | Action |
|------|--------|
| Marketing top nav vs app sidebar | **KEEP** two patterns; **SHARE** logo + CTA tokens only |
| Forms | **REFINE** — prefer `ui/form` where validation; enforce `RADIUS.field` |
| Tables | **SHARE** DataTable/AdaptiveDataView; header type → `TYPE.eyebrow` |
| Charts | **KEEP** ChartContainer + `--chart-*`; sparklines use same tokens |

### Priority (design work order)

1. REMOVE duplicates (stale globals, orphan command input, dead Lottie if unused)  
2. REFINE TYPE/PageHeader adoption + unify MOTION  
3. RESKIN marketing onto semantic brand tokens (light-first)  
4. SHARE voice primitive aliases + chart/table tokens  
5. Desktop token bridge — **APPROVAL REQUIRED**

---

## Phase 3 — External source audit

| Source | Exact opportunities | Constraint |
|--------|---------------------|------------|
| **21st.dev** | Voice orb / waveform / listening·speaking·thinking viz; AI activity / tool-execution feedback | Normalize into GravitreOrb/Wave/Visualizer — no foreign tokens |
| **Aceternity** | Background Beams/Lines, bento-grid, tracing borders, scroll storytelling — marketing hero only | Extract effect; restyle with DS 2.0 |
| **shadcn** | Primitives already installed; MCP ready; use for discovery/examples only | Not the finished design language |
| **Nucleo** | core/ui/sharp/micro/pixel (+ free) on disk `pro+free` | Copy into app; never import from `~/.nucleo/skills` |
| **v0** | Hero concepts, dashboard hierarchy, voice chrome alternatives | Reference only |
| **Motion (Framer)** | Default app + marketing animation | Extend `animations.ts` |
| **GSAP** | Marketing scroll timelines only if Motion insufficient | **APPROVAL per use** |
| **Three/WebGL** | Optional intelligence hero network | Perf/a11y/reduced-motion doc required — **APPROVAL** |

Do not install broad component sets. Prefer selective extract + adapt.

---

## Phase 4 — AI State ↔ Backend State Matrix

| LOCATION | BACKEND CONDITION | FRONTEND STATE | USER LABEL | VISUAL | MOTION | TECH | PERF | BENEFIT | SOURCE OF TRUTH | VERIFY | APPROVAL? |
|----------|-------------------|----------------|------------|--------|--------|------|------|---------|-----------------|--------|-----------|
| Outcomes UI | `verification.confidence=verified` | verified | Verified | Success badge | RESOLVE | CSS/Motion | Low | Honesty | BO models | e2e outcome-states | No |
| Outcomes UI | `accepted_unproven` | accepted | Accepted — not yet confirmed | Warning-tint badge | PULSE soft | CSS | Low | Honesty | BO models | same | No |
| Outcomes UI | `unverified` | unproven | Not verified | Muted badge | none | CSS | Low | Honesty | BO models | same | No |
| Outcomes / runs | `status=failed` | failed | Failed | Destructive | error shake (reduced-safe) | Motion | Low | Clarity | projector / constants | same | No |
| Outcomes / runs | `review_state=flagged_for_review` | flagged | Flagged for review | Warning | PULSE | CSS | Low | Governance | BO models | same | No |
| Approvals | `pending_approval` / `awaiting_approval` | pending | Pending approval | Amber | PULSE | CSS | Low | Actionability | workflows/constants | approvals shots | No |
| Approvals | `approved` / `rejected` | approved/rejected | Approved / Rejected | Success / destructive | RESOLVE | CSS | Low | Closure | approval_status | same | No |
| Intelligence models | Prefer `runtime_status` / confidence_honesty over catalog TRAINED | estimate / trained / data_gate | Estimate / Model / Insufficient data | Module C labels | none for fake TRAINED | CSS | Low | Anti-overclaim | confidence_honesty.py | STA-331 | No — never invent TRAINED as live |
| Agents | `agent_jobs` / SessionStatus / ReActStatus | layer-mapped | Running / Needs input / Failed | Agent status | PULSE / TRACE | Motion | Low | Ops clarity | operators/* | agents shots | No |
| Workflows | Run + step constants | run status | Running / Partial / Failed… | Run chips | TRACE | Motion | Med | Execution path | workflows/constants | runs UI | No |
| Connectors | display connected/syncing/error/disconnected | same | Connected / Syncing / Error / Offline | Status dot | FLOW on syncing | CSS | Low | Trust | connection_health.py | connectors page | No |
| WorkObjects | WorkObjectStatus Literal | same | Identified…Archived | Lifecycle chip | TRACE | CSS | Low | Continuity | work_object_service | WO UI | No |
| Voice PSTN | VoiceSessionStatus | pstn_* | Ringing / In progress… | Call chip | WAVE | CSS | Low | Telephony | voice_gateway_service | ops | No |
| Voice chat duplex | **No backend enum** | VoicePresenceState | Listening / Thinking / Speaking… | Wave + Orb | WAVE | CSS+Motion | Med | UX | Client only | voice-states e2e | Document as client — do not claim PSTN parity |
| Signal priorities | API empty gaps | empty / scored | No priorities / score band | Empty state or score | none / PULSE | CSS | Low | Honesty | signal-scoring-live PARTIAL | priorities API | No — empty is truth |

### BACKEND STATE DOES NOT EXIST (keep client; no silent invent)

- Chat duplex `idle|listening|understanding|thinking|speaking|interrupted|disconnected|error`

---

## Phase 5 — Gravitre Design System 2.0 (proposal)

### Principles
1. Extend existing emerald + graphite language — do **not** transplant Untitled/Beyond/generic purple SaaS.  
2. Purple remains **intentional accent** (schedules/workflow legend already); primary stays emerald.  
3. Dark graphite surfaces for app; marketing may stay light-first on semantic tokens.  
4. One token file of truth: `app/globals.css` + `design-system.ts` + `animations.ts`.

### Token groups to formalize

| Group | Action |
|-------|--------|
| Brand / primary / accent / info | KEEP emerald; document purple as secondary accent only |
| Surface / elevated / border / text | Extend dark graphite clarity |
| Success / warning / error / info | KEEP; map to BO/approval |
| AI / agent / workflow / approval / BO / voice / WorkObject | **Add semantic status tokens** (CSS vars) mapped to matrix above |
| Typography | Enforce TYPE roles; marketing display scale separate but related |
| Spacing / radius / elevation | KEEP RADIUS hierarchy; elevation-1..4 |
| Focus / hover / disabled / loading / skeleton | Document in primitives |
| Dark/light | KEEP dual themes; marketing light lock optional via data-theme |

### Components
Upgrade shared `ui/*` + gravitre specifics in place. No parallel design system package until desktop SHARE is approved.

### Icons
Nucleo canonical; semantic map (Agent, Workflow, Run, Connector, Approval, Voice states, BO honesty). Copy components into repo — never import from `~/.nucleo`.

---

## Phase 6 — Gravitre Motion System 1.0 (proposal)

### Concepts → usage

| Concept | Meaning | Use | Intensity |
|---------|---------|-----|-----------|
| FLOW | Work moving between systems | Connector sync, handoffs | Low |
| PULSE | Intelligence active | Agent active, pending approval, monitoring | Subtle |
| WAVE | Voice/audio | Listening / speaking | Medium, reduced→static bars |
| ORBIT | Multi-agent / tools coordinating | Selective orchestration viz | Rare |
| TRACE | Step progress | Workflows, tool calls | Low |
| RESOLVE | Successful completion | BO verified, approve, sync done | Brief |

### Tokens
Unify `MOTION` + `animations.timing` into one export. Durations: micro 150 / ui 220–250 / major 400. Always `useMotionPrefs()`.

### Canonical primitives (one implementation each)

| Primitive | Implementation plan | Consumers |
|-----------|---------------------|-----------|
| GravitreWave | Alias `GravitreVoiceWaveform` in `voice-presentation.tsx` | Composer, presence, marketing demos via import |
| GravitreOrb | Extract from `VoiceOrbTakeover` | Takeover composes; no surface forks |
| VoiceStateVisualizer | Mapper VoicePresenceState → Wave/Orb props | Presence / composer — **no** second DOM |

### CI drift extension
Preserve `check-chat-surface-drift.mjs`. Add GravitreOrb/Wave/Visualizer ownership. **Mutation-test** before program closure (Class B).

### Live cross-surface verification
Side-by-side: `/ai` voice states, e2e voice-states shots, marketing demo import, desktop when shared.

### Prohibited
MarketingGravitreOrb forks; GSAP for ordinary UI; WebGL in app chrome; motion that invents backend states.

---

## STOP (implementation)

Phases 2–6 are proposals. Implementation begins only after approval of Phase 8 pilots / Phase 9 token work.

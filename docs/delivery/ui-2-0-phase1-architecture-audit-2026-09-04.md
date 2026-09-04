# GRAVITRE UI 2.0 — Phase 1 Read-Only Architecture Audit

**Date:** 2026-09-04  
**Mode:** READ-ONLY — no code changes, no installs  
**Sequencing gate:** PASS — `docs/delivery/ui-2-0-sequencing-gate-closure-2026-09-04.md`

---

## 1. Program sequencing confirmation

| Prerequisite | Status for UI sequencing |
|--------------|--------------------------|
| Voice / dormant-call / unnarrowed / Identity / Gateway / Eval / CRAG / Context Engine / Memory / Work Objects / Signal / Department | **CLOSED** (human smoke waived; residuals honesty-only) |

**Gate:** PASS. Phase 1 audit authorized.

---

## 2. Repository / access verification

| Area | Path | Access |
|------|------|--------|
| Web + marketing | `apps/web` | Verified |
| Desktop | `apps/desktop` (Tauri 2) | Verified |
| Extension | `apps/extension` (MV3 vanilla) | Verified |
| Internal docs | `apps/internal-docs` | Verified |
| Backend | `backend` (FastAPI) | Verified |
| Mobile app | — | **Absent** |
| Shared `packages/` | — | **Empty / unused** |
| CI | `.github/workflows/ci.yml` + many live smokes | Verified |
| Prod health (gate tip) | `api.gravitre.app` `161df8f8…` | Verified at gate closure |

---

## 3. Frontend architecture by surface

| Surface | Framework | Notes |
|---------|-----------|-------|
| **Marketing** | Next.js 16.2 / React 19 — `app/(marketing)/` | Same app as product web |
| **Web app** | Same Next app — `app/ai`, agents, connectors, runs, marketplace… | Primary surface |
| **Mobile** | None | Responsive web only |
| **Desktop** | Vite + Tauri 2 — `apps/desktop` | Isolated CSS island; does not consume web UI |
| **Extension** | Vanilla MV3 | Out of Design System 2.0 primary path unless later scoped |

---

## 4. Package manager + Node architecture

| Item | Finding |
|------|---------|
| Practice | **pnpm** (CI `pnpm/action-setup@v4` v10; Node **22**) |
| Formal workspaces | **No** `pnpm-workspace.yaml` / root `workspaces` |
| Lockfiles | Root + `apps/web` + `apps/desktop` each have `pnpm-lock.yaml`; root also has `package-lock.json` |
| `packageManager` / `engines` | Absent on root/web |
| Risk | Root vs `apps/web` dependency skew (e.g. lucide versions) |

---

## 5–6. Existing Gravitre design system + tokens

| Source | Role |
|--------|------|
| `apps/web/app/globals.css` | **Canonical** — shadcn CSS vars, `@theme inline`, voice `.gv-wave-*` / `.gv-orb-*`, elevation |
| `apps/web/lib/design-system.ts` | TYPE / RADIUS / MOTION / INTERACTION class tokens |
| `apps/web/lib/animations.ts` | Framer Motion timing/easing/variants + `useMotionPrefs()` |
| `apps/web/lib/department-theme.ts` | Department tints |
| `apps/web/styles/globals.css` | **Stale scaffold** — not imported by layout |
| `apps/desktop/src/styles.css` | Separate hardcoded palette |

**Classification:** KEEP + EXTEND canonical web tokens → Design System 2.0. REMOVE DUPLICATE stale `styles/globals.css` after confirm. SHARE tokens into desktop later (APPROVAL REQUIRED for layout).

---

## 7–8. Shared components + duplicates

**Canonical / KEEP**

- `components/ui/*` (58 shadcn primitives)
- `SharedChatComposerControls`, `GravitreVoiceWaveform`, `VoiceOrbTakeover`, `GravitreChatAvatar`

**SHARE / RESKIN / REMOVE DUPLICATE candidates**

| Item | Paths | Action |
|------|-------|--------|
| Button vs IconButton | `ui/button.tsx`, `gravitre/icon-button.tsx` | REFINE — unify token usage |
| Avatars | `ui/avatar`, `user-account-avatar`, `agent-identity-avatar`, `gravitre-chat-avatar`, `chat-avatars` | SHARE semantics; keep roles |
| Composers | `shared-chat-composer-controls` vs `ai-command-input` | REFINE — document roles; avoid second chat chrome |
| Decorative orbs | `floating-orb`, `GlowOrb`, `PulsingOrb`, `AgentOrb` | KEEP separate from voice orb; normalize tokens |

---

## 9–10. Icon architecture + Nucleo readiness

| Library | Status |
|---------|--------|
| lucide-react | Primary (`components.json` iconLibrary) |
| @phosphor-icons/react | Intelligence/admin (~35 files) |
| Nucleo | ~1080 SVGs under `public/icons/nucleo/` + `nucleo-icon.tsx` — **wrapper unused at call sites** |
| Nucleo CLI/skills/MCP | **Not configured** in-repo |

**Proposal:** Nucleo becomes canonical for UI 2.0 after setup; map semantic icons; migrate Lucide/Phosphor gradually. Inventory before broad replace.

---

## 11. Existing motion architecture

| Layer | Finding |
|-------|---------|
| Default | `framer-motion` ^12.38.0 |
| Tokens | `lib/animations.ts` (timing micro/ui/major/slow; reduced-motion via `useMotionPrefs`) |
| CSS voice | `.gv-wave-*` bars; orb under `prefers-reduced-motion` |
| Lottie | Present for select effects |
| GSAP / Three / `motion` package | **Absent** |

Existing doc comment already names “GRAVITRE MOTION SYSTEM” — extend into Motion System 1.0 (FLOW/PULSE/WAVE/ORBIT/TRACE/RESOLVE), do not invent a second stack.

---

## 12–13. Chat/voice drift + CI guard

**Already consolidated:** waveform + orb live in `voice-presentation.tsx`; composer mounts them via `SharedChatComposerControls`.

**CI:** `scripts/check-chat-surface-drift.mjs` in `.github/workflows/ci.yml` (web job).

Protects: single waveform/orb owner files; shared composer on `/ai` + agent chat; retired Text\|Voice / Speak / Dictate; avatar states; reduced-motion CSS.

**Gaps vs UI 2.0 §19–20:** Guard does not yet name `GravitreOrb` / `GravitreWave` / `VoiceStateVisualizer`; desktop/marketing not in walk scope; no mutation-test proof recorded for the guard itself (Class B — required before program closure).

---

## 14–19. MCP / tool readiness

| Tool | CLI | MCP in-repo | Enabled | Auth in env examples | Test | Role |
|------|-----|-------------|---------|----------------------|------|------|
| 21st.dev | Unknown / not wired | No | No | `API_KEY_21ST` **absent** from `.env.example` | Not run | AI/voice refs |
| Aceternity | Unknown / not wired | No | No | `API_KEY_ACETERNITY_UI` **absent** | Not run | Marketing effects |
| shadcn | Yes (`shadcn` ^4) | No `.cursor/mcp.json` | Components present | N/A | components.json active | Primitives |
| Nucleo | Not setup | No | Assets on disk only | License not in source (correct) | Unused wrapper | Icons |
| v0 | External | No | — | — | — | Prototyping |

Cursor plugins present (Linear, Vercel, Supabase, etc.) — unrelated to UI 2.0 stack.

**Phase 7 (after approval):** configure shadcn MCP, Nucleo skills, verify 21st/Aceternity integrations without fabricating MCP support.

---

## 17–18. Exact 21st.dev / Aceternity opportunities (selective)

**21st.dev (normalize into Gravitre):** reactive orb, waveform, listening/speaking/thinking viz, tool-execution feedback — **reference only**; canonical primitives stay `GravitreOrb` / `GravitreWave` / `VoiceStateVisualizer`.

**Aceternity (marketing only):** Background Beams/Lines, tracing borders, bento, scroll storytelling for hero — extract effects, replace foreign tokens.

---

## 20–23. v0 / Motion / GSAP / WebGL

| Tech | Recommendation |
|------|----------------|
| v0 | Prototype marketing hero, dashboard hierarchy, voice chrome alternatives — never wholesale replace screens |
| Motion (Framer) | Default animation layer; extend existing `animations.ts` |
| GSAP | Marketing scroll timelines only if Motion insufficient — APPROVAL REQUIRED per use |
| Three/WebGL | Hero intelligence network **candidate only**; requires perf/a11y/reduced-motion doc — APPROVAL REQUIRED |

---

## 24–26. Proposed Design System 2.0 / Motion 1.0 / Nucleo (proposals — not implemented)

### Design System 2.0
Extend `globals.css` + `design-system.ts`: brand purple as intentional accent; dark graphite surfaces; status tokens for BO confidence, approval, connector display, WorkObject, voice presence; unify Button/IconButton; deprecate stale globals; document dark/light.

### Motion System 1.0
Map existing timing to FLOW / PULSE / WAVE / ORBIT / TRACE / RESOLVE; keep `useMotionPrefs` mandatory; voice bars/orb already WAVE; agent activity = PULSE; workflow steps = TRACE; success = RESOLVE.

### Nucleo
Setup CLI → inventory → semantic map (Agent, Workflow, Run, Connector, Approval, Voice states, BO honesty) → gradual replace Lucide/Phosphor.

---

## 27. AI State ↔ Backend State Matrix (excerpt)

| Frontend intent | Backend source of truth | Approval needed? |
|-----------------|-------------------------|------------------|
| BO Verified / Accepted / Not verified | `verification.confidence`: `verified` \| `accepted_unproven` \| `unverified` | No |
| BO Failed / Flagged | run/outcome `status` + `review_state=flagged_for_review` | No |
| Pending / Approved / Rejected | `approval_status` + run `pending_approval` / `awaiting_approval` | No |
| Module C TRAINED | Prefer `runtime_status` / `confidence_honesty` over catalog `ModelStatus.TRAINED` | No — never show catalog TRAINED as live proof |
| Agent running | Layer-specific: `agent_jobs.status` / `SessionStatus` / `ReActStatus` | No |
| Workflow run | `workflows/constants.py` run statuses | No |
| Connector | `resolve_display_connector_status` → connected/syncing/error/disconnected | No |
| WorkObject | `WorkObjectStatus` Literal in `work_object_service.py` | No |
| Voice **PSTN** | `VoiceSessionStatus` pending→completed/failed… | No |
| Voice **chat duplex** UI | `VoicePresenceState` client-only | **BACKEND STATE DOES NOT EXIST** — keep as client UX; do not claim PSTN parity; documenting as client state OK |

Full enum inventory: see explore audit (BusinessOutcome models, workflows/constants, operators/schemas, voice_gateway_service, work_object_service, confidence_honesty).

---

## 28–30. Shared primitive architecture

| Primitive | Current | Target |
|-----------|---------|--------|
| GravitreWave | `GravitreVoiceWaveform` in `voice-presentation.tsx` | Rename/alias; **one** implementation |
| GravitreOrb | Inner circle of `VoiceOrbTakeover` | Extract presentational `GravitreOrb`; takeover composes it |
| VoiceStateVisualizer | Implicit in presence/composer | Thin mapper `VoicePresenceState` → Wave/Orb props — **no** second bar/orb DOM |

**Consumers:** Marketing (demo only via shared import), Web (required), Desktop (adapter later — APPROVAL), Mobile N/A.

**Forbidden:** MarketingGravitreOrb / WebGravitreOrb duplicates.

---

## 31–33. CI drift extension + verification plans

### Extension proposal
1. Preserve all current allowlists/forbiddens.
2. Add `GravitreOrb` / `GravitreWave` / `VoiceStateVisualizer` to ownership rules.
3. Forbid `<GravitreOrb` / hand-rolled bars outside `VOICE_UI_DEFINITIONS`.
4. Optionally require desktop import path when desktop adopts shared package.

### Independent verification (Class B) — before program closure
1. Disposable branch.
2. Deliberately reintroduce local 5-bar waveform outside allowlist.
3. Confirm `check-chat-surface-drift.mjs` **FAILS**.
4. Discard branch; confirm clean PASS.
5. Document evidence in delivery artifact.

### Live cross-surface verification (Class C)
Side-by-side screenshots: web `/ai` voice states + e2e voice-states shots + marketing demo if any + desktop when wired. Positive confirmation, not “guard silent.”

---

## 34. Material UX/layout recommendations — APPROVAL REQUIRED

| Current | Proposed | Why | Risk | Status |
|---------|----------|-----|------|--------|
| Desktop isolated CSS / green accent | Adopt Design System 2.0 tokens | Cross-surface identity | Medium | **APPROVAL REQUIRED** |
| Dual composers (chat vs command) | Keep roles; forbid second chat chrome | Drift history | Low | APPROVAL if merge |
| Marketing FloatingOrb vs voice orb | Keep decorative separate; shared motion tokens | Clarity | Low | Document |
| Hero WebGL intelligence viz | Optional premium hero | Storytelling | High perf | **APPROVAL REQUIRED** |
| Nucleo replace Lucide broadly | Phased semantic migration | One icon language | Medium churn | **APPROVAL REQUIRED** for broad replace |
| No mobile app | Responsive web only for UI 2.0 | Scope | — | Confirm scope |

---

## 35. Five-pilot plan (prepare only — no implement)

| Pilot | Focus | Motion | 21st | Aceternity | v0? | GSAP? | WebGL? | Backend states |
|-------|-------|--------|------|------------|-----|-------|-------|----------------|
| 1 Marketing homepage | Brand, hero, CTAs | WAVE/FLOW storytelling | Selective | Beams/bento | Yes | Maybe | Maybe | Real connectors only |
| 2 Dashboard | Hierarchy, metrics, AI activity | PULSE/TRACE restrained | No | No | Optional | No | No | Runs, BO, signals empty-honest |
| 3 Agents | Identity, activity, tools, outcomes | PULSE/ORBIT selective | Thinking viz ref | No | Optional | No | No | jobs/session/ReAct |
| 4 GIBE / Intelligence | Learning honesty, signals | TRACE/RESOLVE | No | No | Optional | No | No | Module C + signal gaps |
| 5 Voice | Orb/wave/listening→speaking | WAVE | Orb/wave refs | No | Yes | No | No | Client presence + PSTN separate; FINAL ≠ visual |

---

## 36–37. Technical + performance risks

| Risk | Mitigation |
|------|------------|
| Root/web dependency skew | Single package manager discipline; install only in `apps/web` unless approved |
| Desktop island drift | Shared package or documented adapter — don’t fork primitives |
| Nucleo unused stockpile | Inventory before replace; don’t double-ship Lucide+Nucleo forever |
| WebGL hero cost | Prefer SVG/Motion; WebGL only with perf budget |
| Voice visual ≠ audio fixed | Waiver closes gate; do not claim human audio PASS |
| Drift guard unproven (Class B) | Mutation test before program closure |
| Signal empty scores | Design empty/gap UI — don’t invent populated priorities |

---

## 38. Recommended implementation sequence (after Phase 7–8 approval)

1. Token cleanup (remove stale globals; extend DS 2.0)  
2. Motion tokens (formalize FLOW…RESOLVE on `animations.ts`)  
3. Canonical primitives (GravitreOrb/Wave/Visualizer aliases)  
4. Extend chat-surface-drift CI + mutation-test the guard  
5. Nucleo setup + semantic map  
6. Base shared component reskin  
7. Five pilots in order: Marketing → Dashboard → Agents → GIBE → Voice (visual)  
8. Desktop adapter (if approved)  
9. Cross-platform + Final QA + Class B mutation proof  

---

## STOP

Phase 1 complete. **No code modified. No dependencies installed. No reskin started.**

Awaiting explicit approval to proceed to Phase 2–6 proposals depth / Phase 7 tool configuration / or pilot implementation.

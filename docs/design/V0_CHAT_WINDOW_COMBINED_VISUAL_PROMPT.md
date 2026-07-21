# v0 prompt — Combined chat window visual pass (timestamps/history + themes + actions + BusinessOutcome)

Paste into v0 after syncing from `main` at tip **`9f7771ac`** (or later HEAD). **Presentation only.**

Functional baselines are CLOSED — do not re-litigate correctness:

| Surface | Status | Tip |
|---------|--------|-----|
| Chat timestamps / history buckets / pin / archive / search / Edit & resend | CLOSED (`docs/delivery/chat-timestamps-history-live.json`) | `9f7771ac` |
| BusinessOutcome DTO + shared renderer | CLOSED (`docs/delivery/business-outcome-live.json`) | `9f7771ac` |

---

## Bundle (one coherent pass — not two rounds)

1. **Timestamps / history** — relative + hover-exact stamps, message clustering, Pinned / Today / Yesterday / Previous 7 Days / Previous 30 Days / Month labels, pin/archive icons, search, Edit & resend.
2. **Chat window redesign** — message actions (Copy Text, Regenerate, Copy Link/Share, Save Question) + **8 light/dark background themes**.
3. **BusinessOutcome in chat** — same `BusinessOutcomeView` card, styled so it belongs in the redesigned transcript (no DTO / projection / undo logic changes).

Personality: **Module D calm-expert** — operator console, not consumer chat skin. Read `docs/delivery/module-d-gravitree-voice.md`.

---

## Hard freeze (do not change)

- Sort order or bucket-assignment logic (`apps/web/lib/conversation-history-groups.ts`)
- Timestamp accuracy / source of truth (`apps/web/lib/chat-message-time.ts` — still uses `metadata.created_at` from backend)
- BusinessOutcome DTO contract or rendering *logic* (`apps/web/components/gravitre/business-outcome/business-outcome-view.tsx` — CSS/layout density OK; no fabricated sections)
- Any data contract, write path, or governance behavior

If a design needs data the current shape does not provide → **stop and report** a small explicit backend addition. Do not invent fields in the UI.

---

## Primary files (extend, do not fork)

| Area | Path |
|------|------|
| AI workspace shell | `apps/web/app/ai/_components/ai-workspace.tsx` |
| History sidebar | `apps/web/components/gravitre/assistant/conversation-sidebar.tsx` |
| Bucket grouping (logic frozen) | `apps/web/lib/conversation-history-groups.ts` |
| Timestamp helpers (logic frozen) | `apps/web/lib/chat-message-time.ts` |
| Execution / BusinessOutcome in chat | `apps/web/components/gravitre/assistant/chat-execution-panel.tsx` |
| BusinessOutcome renderer | `apps/web/components/gravitre/business-outcome/business-outcome-view.tsx` |
| Brand shell | `apps/web/components/gravitre/app-shell.tsx` |

---

## Direction choice (pick one before implementing)

### Direction A — Operator Console (recommended)

Calm navy/slate field, restrained emerald accent, low-chroma bubbles that read as **transcript panels** not iMessage. Sidebar is a dense operator list (bucket labels as quiet uppercase metadata). Themes tint the **canvas wash** only; chrome and sidebar stay stable. Actions appear as a quiet icon rail on hover/focus.

### Direction B — Editorial Desk

Slightly more paper/ink contrast in light mode; assistant turns as open prose with a thin left rule instead of filled bubbles; user turns as compact right-aligned cards. Themes are paper textures / cool desk washes. Strong hierarchy for BusinessOutcome as a “completed work” document inset.

### Direction C — Focus Stage

Dark-first default; transcript centered with generous max-width; sidebar collapses to icon+pin density. Themes are subtle stage backdrops (grid / gradient wash — keep Gravitree, avoid purple glow). Message actions in a single overflow menu to reduce chrome.

**Default recommendation if no preference stated: Direction A.**

**CHOSEN 2026-07-21: Direction A — Operator Console** (see `docs/delivery/chat-v0-operator-console-direction-a.md`).

---

## Visual requirements (all directions)

### Transcript

- Relative timestamp visible per clustering rules; **exact** time on hover/`title` (already wired — restyle tooltip only)
- Message clustering spacing must still match `shouldShowClusterTimestamp` (2-minute same-role cluster)
- User vs assistant hierarchy clear without loud bubble chrome
- `Edit & resend` remains discoverable on user turns

### History sidebar

- Bucket labels: Pinned, Today, Yesterday, Previous 7 Days, Previous 30 Days, Month (from grouping helper — do not rename logic)
- Pin / archive affordances remain; search remains content-capable (API already supports body search)
- Relative time on rows stays secondary to title

### Message actions (assistant turns; user where applicable)

| Action | Expected behavior | Likely gap |
|--------|-------------------|------------|
| Copy Text | Clipboard of message body | Frontend OK |
| Regenerate | Re-run last assistant turn via existing chat send/regenerate path if present on `/ai`; else report | May need wiring to existing stream path — no fake success |
| Copy Link / Share | Copy deep link to conversation (+ message fragment if supported) | Report if no stable public/share URL exists |
| Save Question | Persist user question for later | **Likely needs backend** — report; do not fake local-only “saved” that disappears |

### Background themes

- **8 themes**, each with **light + dark** variants (16 total appearances), selectable from chat chrome
- Persist preference in `localStorage` (presentation preference only)
- Themes must not break contrast for timestamps, actions, BusinessOutcome, or sidebar
- Avoid generic AI purple / glow / cream-serif clichés

Suggested theme IDs (rename for brand fit, keep count = 8):

1. `slate` — default calm operator
2. `mist` — cool soft wash
3. `pine` — emerald-tinted field
4. `graphite` — high-contrast graphite
5. `sand` — warm neutral (restrained)
6. `ink` — deep ink / paper
7. `glacier` — cool blue-gray
8. `midnight` — near-black stage

### BusinessOutcome

- Keep `BusinessOutcomeView` as the only renderer
- Density `chat` must sit cleanly inside themed transcript
- No Impact / Related / Dependencies / History fabrications

---

## Post-implement verification (mandatory before Done)

Re-run the **same** live checks already proven — presentation change only, zero functional regression:

1. Timestamp accuracy (API `created_at` == DB)
2. Bucket rendering (labels + order)
3. Pin / archive / content search
4. Edit & resend

Capture live screenshots:

- Finished redesign **light** and **dark**
- At least **two** different background themes selected
- One **BusinessOutcome** completion card in transcript context
- History sidebar showing **real** bucket labels

Then: commit → push → merge to `main` → deploy → confirm `/health` `git_sha` → attach evidence paths under `docs/delivery/`.

---

## Explicit report-backs (do not workaround)

Open questions for Cursor/backend if design requires them:

1. **Save Question** persistence API / table?
2. **Copy Link** — canonical URL shape for conversation + message?
3. **Regenerate** — does `/ai` already have a first-class regenerate path equivalent to agent chat?

---

## Constraints

- No new npm dependencies unless already in workspace
- No backend/API contract changes in the v0 PR (gaps → report)
- TypeScript strict; `pnpm typecheck` in `apps/web`
- List files changed + manual checklist at end

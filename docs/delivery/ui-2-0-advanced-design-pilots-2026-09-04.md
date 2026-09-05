# Advanced Design pilots — shipped (2026-09-04)

**Program:** Gravitre 2.0 Advanced Design Integration (augmentation)  
**Approval:** Cesar approved research board → recommended pilots  
**Board:** `docs/delivery/ui-2-0-advanced-design-research-board-2026-09-04.md`

---

## What shipped

### 1. Agent Elements ADAPT (Gravitre-native — no registry install)

Foreign `shadcn` Agent Elements registry install was abandoned (hung; would pull unused deps). Built retokened ADAPT under `apps/web/components/gravitre/agent-ui/`:

| Component | Role | Wired into |
|-----------|------|------------|
| `tool-execution-group.tsx` | Collapses multi-tool chip rows | `chat-transcript.tsx` |
| `thinking-row.tsx` | Collapsible waiting/thinking status | `chat-transcript.tsx` |
| `plan-approval-chrome.tsx` | Plan/approval header chrome | `chat-execution-panel.tsx` |

**Not done:** Agent Elements `agent-chat` shell (hard reject). Clarify/QuestionTool ADAPT deferred — no clean single clarify surface without layout risk.

`tool-chip.tsx` outcome chips use `STATUS.*` (semantic tokens).

### 2. Canonical Orb / Wave breathe polish

- `voice-presentation.tsx`: EMA amplitude smoothing (~0.82/0.18), longer transform ease (~180ms), calmer wave durations; reactive bar height transition 160ms  
- `globals.css`: `.gv-orb-user` / `.gv-orb-agent` pulse slowed to ~1.65s / ~2.45s with softer scale/glow  

No Orb/Wave forks. Visual-only; does **not** claim Voice human audio PASS.

### 3. Marketing atmosphere (marketing only)

- `marketing-background-lines.tsx` — Aceternity-inspired lines, Gravitre primary/info gradient  
- Mounted **below-fold** on home “Built for operators” section (`app/(marketing)/page.tsx`)  
- Hero beams unchanged (`HeroBrandBeams`)

---

## Explicit non-claims

- No layout / IA change intended (same regions, chrome wrap only)  
- No Aceternity on chat/dashboard ops  
- No WebGL voice orb in operational chat  
- Voice functional human verify still separate / waived only for UI reskin program  
- Package deps for Agent Elements registry **not** added  

---

## Verification

- `npx tsc --noEmit` (apps/web) — **PASS** (2026-09-04 local)  
- `node scripts/check-chat-surface-drift.mjs` — **PASS** (`chat-surface-drift PASS`)

Deploy + live visual check: merge → Vercel Ready → spot-check `/`, chat tool group, approval chrome, Talk orb breathe.

---

## Customer surfaces

No new prices, claims, badges, or Enable toggles. **(a)** Visual augmentation only per approved research board.

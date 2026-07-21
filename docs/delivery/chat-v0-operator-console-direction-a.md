# Chat v0 — Direction A (Operator Console) implementation

**Chosen:** Direction A — Operator Console  
**Scope:** Presentation only (combined timestamps/history + themes + message actions + BusinessOutcome density).  
**Baseline tip before ship:** `9f7771ac` (functional closures).

## What changed

| Area | Change |
|------|--------|
| Bubbles | Low-chroma transcript panels (`chat-typography.ts`) — not solid iMessage emerald |
| Timestamps | Unchanged logic; quieter role labels + tooltip chrome |
| Sidebar | Bucket label tracking tightened (logic frozen) |
| Themes | 8 canvas washes via `data-chat-theme` + `localStorage` (`chat-canvas-themes.ts`) |
| Actions | Copy text, Regenerate (resend prompt), Copy link (`/ai?c=&m=`), Save Question affordance |
| BusinessOutcome | Chat density: document-inset left rule, calmer fill |

## Explicit gaps (not fabricated)

1. **Save Question** — no durable API. Button shows toast explaining backend needed.
2. **Copy Link** — copies `/ai?c={conversationId}&m={messageId}`. Conversation deep-link works; **message scroll-to (`m=`) is not wired** (presentation URL shape only until a small frontend deep-link handler is added).
3. **Regenerate** — implemented as truncate-to-prompting-user + `runChat` (same append-only pattern as Edit & resend). Not a server-side regenerate endpoint.

## Frozen (untouched)

- `conversation-history-groups.ts`
- `chat-message-time.ts` helpers
- BusinessOutcome DTO / projection / undo logic

## Post-deploy verification checklist

1. `/health` tip advances past pre-ship SHA  
2. Relative timestamps + hover exact still work  
3. Bucket labels still render  
4. Pin / archive / search still work  
5. Edit & resend still works  
6. Screenshots: light + dark, ≥2 themes, BusinessOutcome in transcript, sidebar buckets  

Evidence paths (fill after live capture): `docs/delivery/chat-v0-operator-console-evidence/`

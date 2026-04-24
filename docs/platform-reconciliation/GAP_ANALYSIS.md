# Gap Analysis — Cursor vs v0

## 1) Backend modules without UI
- **Org membership admin**: `/api/org/members` exists, no UI surface.
- **Operator links**: first‑class links exist in DB + BE; no UI to manage.

## 2) UI pages without backend support
- `/environments` → placeholder only; no backend admin model.
- `/settings` → placeholder only; no backend settings model.

## 3) Duplicated or conflicting features
- **Connectors vs Integrations**: v0 uses `/connectors`; Cursor uses `/integrations`. `/connectors` is legacy redirect.
- **Sources routing**: v0 uses `/sources`; Cursor canonical UI is `/rag/sources` with `/sources` redirect.
- **RAG query**: v0 uses `/chat`; Cursor uses `/chat` as RAG query UI (ok, but not labeled RAG).

## 4) Routes to remove or rename
- Remove v0 `/connectors` route in favor of `/integrations`.
- Keep `/sources` as a redirect to `/rag/sources` (or rename v0 to `/sources` → `/rag/sources`).

## 5) Pages missing from platform
- **Environment admin** UI + BE for multi‑env management (currently header only).
- **Settings** UI + BE for org‑level configuration.
- **Operator link management** UI (agent handoffs).

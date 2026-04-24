# DC-10 — Ingestion UI (Controlled Source Types)

**Status:** Implemented  
**Authority:** Brand Spec + DC-00 + RB-00  
**Source Types:** manual | internal | external | product | support

---

## Proxy Routes (Next.js)

- GET/POST `/api/rag/sources`
- GET/PATCH `/api/rag/sources/[id]`
- GET `/api/rag/documents`
- GET `/api/rag/documents/[id]`
- POST `/api/rag/ingest`
- GET `/api/rag/ingest/[id]`
- GET `/api/org/members`

All calls are same‑origin and forward Authorization. FASTAPI_BASE_URL required.

---

## Frontend API Helpers

`apps/web/lib/rag-api.ts`  
Includes `RagSourceType` union, `RagSource`, and helper functions for all DC‑10 routes.

---

## Routes

| Route | Description |
|-------|-------------|
| `/rag/sources` | List sources; admin “New Source” CTA |
| `/rag/sources/new` | Create source form (admin‑only) |
| `/rag/sources/[id]` | Source detail + documents list + ingest CTA |
| `/rag/ingest` | Ingest UI (text or chunks JSON) |
| `/rag/ingest/[id]` | Ingest job status |
| `/rag/documents/[id]` | Document metadata; admin chunk toggle |

---

## Admin Gating

- Uses `GET /api/org/members` to determine role.  
- Non‑admin UI is disabled with a calm info message.  
- Backend still enforces RB‑00.

---

## UI States

All pages implement **loading**, **empty**, **error**, and **disabled (non‑admin)** states.  

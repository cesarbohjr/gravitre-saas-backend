# IN-00 — Connector Registry + Secrets Implementation

**Status:** Implemented  
**Authority:** docs/MASTER_PHASED_MODULE_PLAN.md Part V  
**Dependencies:** BE-00, RB-00 (admin-only)

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/connectors | Admin | List connectors (no secrets) |
| POST | /api/connectors | Admin | Create connector |
| GET | /api/connectors/:id | Admin | Get connector (no secrets) |
| PATCH | /api/connectors/:id | Admin | Update config/status |
| POST | /api/connectors/:id/secrets | Admin | Set secret (never returned) |

---

## Request/Response

### POST /api/connectors
**Request:** `{ "type": "slack"|"email"|"webhook", "config": {} }`  
**Response 201:** `{ "id": "uuid", "type": "...", "status": "active", "config": {} }`

### POST /api/connectors/:id/secrets
**Request:** `{ "key_name": "token", "value": "xoxb-..." }`  
**Response 200:** `{ "key_name": "token", "message": "Secret stored" }`  
**503:** CONNECTOR_SECRETS_ENCRYPTION_KEY not set

---

## Env Vars

| Var | Required | Description |
|-----|----------|-------------|
| CONNECTOR_SECRETS_ENCRYPTION_KEY | For secrets | Fernet key from `Fernet.generate_key()` |

---

## Tables

- **connectors:** id, org_id, type, status, config, created_at, updated_at, created_by
- **connector_secrets:** id, org_id, connector_id, key_name, encrypted_value (never exposed)

---

## Acceptance Criteria

- [x] Create connector config without secrets
- [x] Store secrets securely (Fernet encrypted)
- [x] Never return secrets to FE
- [x] RLS org-scoped
- [x] Admin-only

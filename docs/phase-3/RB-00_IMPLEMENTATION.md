# RB-00 — Roles & Membership Implementation

**Status:** Implemented  
**Authority:** docs/MASTER_PHASED_MODULE_PLAN.md Part V  
**Dependencies:** BE-00

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/org/members | Admin | List org members |
| POST | /api/org/members/invite | Admin | Stub: create invite (no email) |
| PATCH | /api/org/members/:id | Admin | Update member role |
| DELETE | /api/org/members/:id | Admin | Remove member |

---

## Request/Response

### GET /api/org/members
**Response 200:**
```json
{
  "members": [
    { "id": "uuid", "user_id": "uuid", "role": "admin"|"member", "created_at": "..." }
  ]
}
```

### POST /api/org/members/invite
**Request:** `{ "email": "optional" }`  
**Response 201:** `{ "invite_token": "stub-...", "message": "Invite created (stub); no email sent" }`

### PATCH /api/org/members/:id
**Request:** `{ "role": "admin"|"member" }`  
**Response 200:** `{ "id": "uuid", "user_id": "uuid", "role": "admin"|"member" }`  
**400:** Cannot demote self if only admin

### DELETE /api/org/members/:id
**Response 200:** `{ "id": "uuid", "message": "Member removed" }`  
**400:** Cannot remove self if only admin

---

## Env Vars

None new. Uses existing Supabase config.

---

## Audit Events

| Action | When |
|--------|------|
| org.member.listed | GET /api/org/members |
| org.member.invited | POST invite (stub) |
| org.member.updated | PATCH role change |
| org.member.removed | DELETE member |

---

## Acceptance Criteria

- [x] Admin can list members
- [x] Admin can update roles (PATCH)
- [x] Admin can remove members (DELETE)
- [x] Non-admin receives 403 on mutate
- [x] Cannot demote/remove self if only admin
- [x] All changes write audit events
- [x] organization_members.role CHECK (admin|member)

---

## Non-Goals

- No SSO provisioning
- No complex RBAC matrices
- Invite is stub only (no email delivery)

# BE-00 Hardening — Change List

**Authority:** BE-00 Hardening + Phase-1 Next Steps task.  
**Scope:** Backend only; no RAG/workflows/operators.

---

## A1) JWT Validation Hardening

- **Issuer verification:** JWT `iss` must match Supabase project issuer. Config: `SUPABASE_JWT_ISSUER` (optional; default derived from `SUPABASE_URL` + `/auth/v1`).
- **Audience:** Configurable via `SUPABASE_JWT_AUDIENCE` (default `"authenticated"`).
- **Clock skew:** `SUPABASE_JWT_LEEWAY_SECONDS` (default 60s) applied to exp/iat.
- **401 reason logging:** On auth failure, log category only: `missing_token` | `invalid_signature` | `expired` | `invalid_claims`. Raw tokens are never logged.
- **Files:** `backend/app/config.py`, `backend/app/auth/dependencies.py`, `.env.example`.

---

## A2) Org Membership Semantics (Single-Org-per-User)

- **Missing membership row:** Treated as authenticated but not onboarded. `/api/auth/me` returns `org_id: null`. Log warning with `user_id` (no PII beyond what is already returned).
- **Multiple membership rows:** Treated as data inconsistency. Return 500, log error with `stop_condition=multiple_membership_rows`. Defended via `limit(2)` and `len(r.data) > 1`.
- **File:** `backend/app/auth/dependencies.py`.

---

## A3) Separation of AuthN vs Org Context

- **`get_current_user`:** Strictly auth: JWT decode/verify only. No org lookup.
- **`get_org_context`:** Enrichment only. Not required for 200; `/api/auth/me` returns 200 with `org_id: null` when no membership.
- **No change** to contract; behavior already matched.

---

## A4) CORS Tightening (Dev-Safe, Scalable)

- **Origins:** Only `http://localhost:3000` and `http://127.0.0.1:3000` (HTTPS variants removed for dev).
- **Headers:** Explicit allow list: `Authorization`, `Content-Type`, `X-Request-Id`.
- **Credentials:** `allow_credentials=False` (Bearer token model). Documented that cookie auth would require a later change.
- **File:** `backend/app/main.py`.

---

## A5) Logging Improvements

- **401:** Log reason category (`missing_token`, `invalid_signature`, `expired`, `invalid_claims`) via `logger.warning("401 auth_failure reason=...")`. No raw token ever logged.
- **x-request-id:** Response header set in middleware; guard added so it is always present.
- **Files:** `backend/app/auth/dependencies.py`, `backend/app/main.py`.

---

## A6) Dependency Hygiene

- **Requirements:** Pinned to major.minor ranges; comment added that no new deps without approval.
- **File:** `backend/requirements.txt`.

---

## Documentation Updates

- **Scalable architecture:** Appended to `docs/phase-0/SA-00_EXECUTION_PLAN.md` (§11): Single Origin via Next.js Reverse Proxy as recommended; rewrites, credentials, and “no FE yet” note.
- **Next Steps:** Appended to same doc (§12): FE-00 as next module; blockers and stop conditions; BE-01 “Onboarding Minimal” optional and gated by MASTER_PHASED_MODULE_PLAN.

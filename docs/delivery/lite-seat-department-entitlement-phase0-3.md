# Lite seat + department entitlement program (2026-08-08)

## Locked product decisions
- **A1** Hard gate: Lite cannot call BUILD / Meson-build APIs; shared UI + backend enforce.
- **B1** Lite may **use** department-assigned workflows; cannot Meson build/edit.
- **C1** Meson Addons catalog codes are real entitlement gates (`require_addon` + feature flags).
- **D1** `department_members.role=admin` = department_manager, scoped to that department.
- **E1** Included Lite seats SoT = `get_plan_for_org` → `features.lite_users`.

## Phase 0 confirmed model
| Dimension | SoT |
|-----------|-----|
| Plan tier | `org_billing.plan_code` → `resolve_entitlements` / `get_plan_for_org` |
| Lite seat | `department_members` (not a plan tier) |
| Meson builder | Plan ≥ Control **and** full seat |
| Meson addons | `subscriptions.meson_addons` → `features.meson_addon_*` |

## What shipped
- `seat_context.py` + `require_full_seat` / `require_addon`
- `department_resource_assignments` table + `/api/departments/*`
- Workflow list filtered to assignments for Lite
- Lite `/api/lite/workflows` prefers assignments
- Shared sidebar progressive disclosure (BUILD locked for Lite); Meson toolbar hidden for Lite
- `/lite` home → shared `/home`
- Voice API gated on `voice_interface` addon
- Lite seats admin summary uses plan `lite_users`

## Verification
- Unit: `backend/tests/billing/test_seat_context_and_addons.py` + tier guards — **18 passed**
- Live dept-manager scope: `python scripts/prove-department-manager-scope.py` → `cross_dept_blocked=True`, `pass: True` (disposable org cleaned)
- Migration applied: `department_resource_assignments` on prod Supabase `smyeexlrqdpymwjmgzqu`
- Deploy: confirm `/health` `git_sha` after push

## Screenshot note
Shared shell evidence: Lite and full seat use `ADMIN_SIDEBAR_NAV` with BUILD items locked (`requiresFullSeat`) for Lite; Meson toolbar hidden when `isLite`. Capture side-by-side after tip deploy by toggling Admin/Lite as org admin, or two accounts.

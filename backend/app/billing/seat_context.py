"""Seat type + department scope — orthogonal to plan tier and Meson addons."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.core.errors import error_detail


def response_error(resp: Any) -> Any:
    return getattr(resp, "error", None)


def resolve_seat_context(client, *, org_id: str, user_id: str) -> dict[str, Any]:
    """Compose org role + department membership into seat/department scope.

    Rules (locked product decisions A1/D1):
    - Org owner/admin = full seat (never forced Lite), org-wide admin.
    - department_members.role=admin = department_manager for that department only.
    - Other department members = Lite seat for that department.
    """
    org_role = None
    try:
        org_resp = (
            client.table("organization_members")
            .select("role")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not response_error(org_resp) and org_resp.data:
            org_role = str((org_resp.data[0] or {}).get("role") or "").strip().lower() or None
    except Exception:
        org_role = None

    is_org_admin = org_role in {"owner", "admin"}
    departments: list[dict[str, Any]] = []
    managed_department_ids: list[str] = []
    member_department_ids: list[str] = []

    try:
        member_resp = (
            client.table("department_members")
            .select("id, department_id, role, departments(id, name, org_id)")
            .eq("user_id", user_id)
            .execute()
        )
        if not response_error(member_resp):
            for row in member_resp.data or []:
                dept = row.get("departments") if isinstance(row.get("departments"), dict) else {}
                if str(dept.get("org_id") or "") != org_id:
                    continue
                dept_id = str(dept.get("id") or row.get("department_id") or "").strip()
                if not dept_id:
                    continue
                role = str(row.get("role") or "").strip().lower()
                entry = {"id": dept_id, "name": dept.get("name") or "Department", "role": role}
                departments.append(entry)
                member_department_ids.append(dept_id)
                if role == "admin":
                    managed_department_ids.append(dept_id)
    except Exception:
        pass

    is_department_manager = bool(managed_department_ids) and not is_org_admin
    # Lite seat: department member who is not an org admin (A1 identity).
    is_lite = bool(member_department_ids) and not is_org_admin
    # Full seat = not Lite (org admins always full; non-members without dept = full/core).
    is_full_seat = not is_lite

    return {
        "org_id": org_id,
        "user_id": user_id,
        "org_role": org_role,
        "is_org_admin": is_org_admin,
        "is_lite": is_lite,
        "is_full_seat": is_full_seat,
        "is_department_manager": is_department_manager or is_org_admin,
        "departments": departments,
        "member_department_ids": member_department_ids,
        "managed_department_ids": managed_department_ids if not is_org_admin else member_department_ids,
        "primary_department": departments[0] if departments else None,
    }


def assert_full_seat(seat: dict[str, Any], *, action: str = "build") -> None:
    if seat.get("is_full_seat"):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=error_detail(
            "Full seat required",
            "UNAUTHORIZED",
            {"reason": "lite_seat_blocked", "action": action},
        ),
    )


def assert_department_manager(seat: dict[str, Any], department_id: str | None = None) -> None:
    if seat.get("is_org_admin"):
        return
    managed = {str(x) for x in (seat.get("managed_department_ids") or [])}
    if not managed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("Department manager role required", "UNAUTHORIZED"),
        )
    if department_id and str(department_id) not in managed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail(
                "Outside department scope",
                "UNAUTHORIZED",
                {"department_id": department_id},
            ),
        )


def list_assigned_resource_ids(
    client,
    *,
    org_id: str,
    department_ids: list[str],
    resource_type: str,
) -> set[str]:
    if not department_ids:
        return set()
    try:
        resp = (
            client.table("department_resource_assignments")
            .select("resource_id, department_id")
            .eq("org_id", org_id)
            .eq("resource_type", resource_type)
            .in_("department_id", department_ids)
            .execute()
        )
        if response_error(resp):
            return set()
        return {str(row.get("resource_id")) for row in (resp.data or []) if row.get("resource_id")}
    except Exception:
        return set()

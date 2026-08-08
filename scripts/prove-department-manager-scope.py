"""Prove department manager cannot assign outside their department (D1)."""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

for candidate in [ROOT / "backend" / ".env.operator.local", ROOT / "backend" / ".env"]:
    if not candidate.exists():
        continue
    for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value

from fastapi import HTTPException  # noqa: E402
from supabase import create_client  # noqa: E402

from app.billing.seat_context import assert_department_manager, resolve_seat_context  # noqa: E402
from app.config import get_settings  # noqa: E402


def main() -> int:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    dept_a = str(uuid.uuid4())
    dept_b = str(uuid.uuid4())
    name = f"dept-scope-probe-{org_id[:8]}"
    print(f"creating disposable org {org_id}")
    client.table("organizations").insert({"id": org_id, "name": name}).execute()
    # Reuse a real auth user so department_members FK succeeds.
    real_user = (
        client.table("organization_members")
        .select("user_id")
        .limit(1)
        .execute()
        .data
        or [{}]
    )[0].get("user_id")
    if not real_user:
        print("FAIL no real user_id available")
        client.table("organizations").delete().eq("id", org_id).execute()
        return 1
    user_id = str(real_user)
    client.table("departments").insert(
        [
            {"id": dept_a, "org_id": org_id, "name": "Dept A", "lite_seat_allocation": 2},
            {"id": dept_b, "org_id": org_id, "name": "Dept B", "lite_seat_allocation": 2},
        ]
    ).execute()
    client.table("department_members").insert(
        {"department_id": dept_a, "user_id": user_id, "role": "admin"}
    ).execute()
    try:
        seat = resolve_seat_context(client, org_id=org_id, user_id=user_id)
        # If this user is also org admin elsewhere, seat may still be full for THIS org
        # when they have no org membership here — expect Lite dept manager.
        assert_department_manager(seat, dept_a)
        blocked = False
        try:
            assert_department_manager(seat, dept_b)
        except HTTPException:
            blocked = True
        client.table("department_resource_assignments").insert(
            {
                "org_id": org_id,
                "department_id": dept_a,
                "resource_type": "workflow",
                "resource_id": "wf-probe-1",
                "assigned_by": user_id,
            }
        ).execute()
        ok = blocked and ("d1" not in str(seat.get("managed_department_ids")) or dept_a in seat["managed_department_ids"])
        print(
            {
                "is_lite": seat["is_lite"],
                "is_org_admin": seat["is_org_admin"],
                "managed": seat["managed_department_ids"],
                "cross_dept_blocked": blocked,
                "pass": blocked is True and dept_a in (seat["managed_department_ids"] or []),
            }
        )
        return 0 if (blocked and dept_a in (seat["managed_department_ids"] or [])) else 1
    finally:
        client.table("department_resource_assignments").delete().eq("org_id", org_id).execute()
        client.table("department_members").delete().eq("department_id", dept_a).execute()
        client.table("departments").delete().eq("org_id", org_id).execute()
        client.table("organizations").delete().eq("id", org_id).execute()
        print(f"cleaned {org_id}")


if __name__ == "__main__":
    raise SystemExit(main())

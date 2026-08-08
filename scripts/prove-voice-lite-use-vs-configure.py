"""B1 live proof: Lite USE vs CONFIGURE + cross_dept_blocked for voice.

Mirrors prove-department-manager-scope.py pattern with disposable org rows.
"""
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

from app.billing.seat_context import (  # noqa: E402
    assert_agent_voice_use,
    assert_voice_configure,
    resolve_seat_context,
)
from app.config import get_settings  # noqa: E402


def main() -> int:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_id = str(uuid.uuid4())
    dept_a = str(uuid.uuid4())
    dept_b = str(uuid.uuid4())
    agent_a = str(uuid.uuid4())
    agent_b = str(uuid.uuid4())
    name = f"voice-b1-probe-{org_id[:8]}"
    print(f"creating disposable org {org_id}")

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
        return 1
    user_id = str(real_user)

    client.table("organizations").insert({"id": org_id, "name": name}).execute()
    client.table("departments").insert(
        [
            {"id": dept_a, "org_id": org_id, "name": "Dept A", "lite_seat_allocation": 2},
            {"id": dept_b, "org_id": org_id, "name": "Dept B", "lite_seat_allocation": 2},
        ]
    ).execute()
    # Lite member (viewer) — not manager
    client.table("department_members").insert(
        {"department_id": dept_a, "user_id": user_id, "role": "viewer"}
    ).execute()
    client.table("agents").insert(
        [
            {
                "id": agent_a,
                "org_id": org_id,
                "name": "Voice Probe A",
                "department": "Dept A",
                "status": "active",
            },
            {
                "id": agent_b,
                "org_id": org_id,
                "name": "Voice Probe B",
                "department": "Dept B",
                "status": "active",
            },
        ]
    ).execute()
    client.table("department_resource_assignments").insert(
        {
            "org_id": org_id,
            "department_id": dept_a,
            "resource_type": "agent",
            "resource_id": agent_a,
            "assigned_by": user_id,
        }
    ).execute()

    try:
        seat = resolve_seat_context(client, org_id=org_id, user_id=user_id)
        configure_blocked = False
        try:
            assert_voice_configure(seat)
        except HTTPException as exc:
            configure_blocked = exc.status_code == 403

        use_assigned_ok = True
        try:
            assert_agent_voice_use(client, seat, org_id=org_id, agent_id=agent_a)
        except HTTPException:
            use_assigned_ok = False

        cross_dept_blocked = False
        try:
            assert_agent_voice_use(client, seat, org_id=org_id, agent_id=agent_b)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            nested = detail.get("details") if isinstance(detail.get("details"), dict) else detail
            cross_dept_blocked = (
                exc.status_code == 403
                and (nested or {}).get("reason") == "cross_dept_blocked"
            )

        passed = (
            bool(seat.get("is_lite"))
            and configure_blocked
            and use_assigned_ok
            and cross_dept_blocked
        )
        print(
            {
                "is_lite": seat.get("is_lite"),
                "is_full_seat": seat.get("is_full_seat"),
                "configure_blocked": configure_blocked,
                "use_assigned_ok": use_assigned_ok,
                "cross_dept_blocked": cross_dept_blocked,
                "pass": passed,
            }
        )
        return 0 if passed else 1
    finally:
        client.table("department_resource_assignments").delete().eq("org_id", org_id).execute()
        client.table("agents").delete().eq("org_id", org_id).execute()
        client.table("department_members").delete().eq("department_id", dept_a).execute()
        client.table("departments").delete().eq("org_id", org_id).execute()
        client.table("organizations").delete().eq("id", org_id).execute()
        print(f"cleaned {org_id}")


if __name__ == "__main__":
    raise SystemExit(main())

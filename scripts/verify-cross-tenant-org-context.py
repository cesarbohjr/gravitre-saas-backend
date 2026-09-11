"""Live cross-tenant authorization test against real production rows.

Runs the actual dependency that every AI endpoint uses for org scoping
(`_resolve_org_context_live`, which `get_org_context` delegates to on a cache
miss) with a real Org A member asking for Org B. No users are created and no rows
are written; this is read-only against production.

Run: railway run python scripts/verify-cross-tenant-org-context.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Python puts this script's own directory on sys.path, not the cwd, so `app` is not
# importable when run as `railway run python ../scripts/...` from backend/.
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

def _pick_triple(client, is_platform_admin, list_member_org_ids):
    """Find a real (user, own org, foreign org) triple that makes a valid test.

    Hardcoding one is fragile: the first candidate tried was a platform admin,
    which legitimately bypasses org scoping, so a "pass" there would have proved
    nothing. This searches for a user who is genuinely scoped.
    """
    rows = (
        client.table("organization_members")
        .select("org_id, user_id")
        .limit(400)
        .execute()
        .data
        or []
    )
    orgs = sorted({str(r["org_id"]) for r in rows if r.get("org_id")})
    seen: set[str] = set()
    for row in rows:
        user_id = str(row.get("user_id") or "")
        if not user_id or user_id in seen:
            continue
        seen.add(user_id)
        if is_platform_admin(client, user_id):
            continue
        memberships = list_member_org_ids(client, user_id)
        if not memberships:
            continue
        foreign = [o for o in orgs if o not in memberships]
        if not foreign:
            continue
        return user_id, memberships[0], foreign[0], memberships
    return None, None, None, []


async def main() -> int:
    from app.auth.dependencies import _OrgContextForbidden, _resolve_org_context_live
    from app.auth.platform_admin import is_platform_admin
    from app.config import get_settings
    from app.services.org_membership import list_member_org_ids
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)

    USER_A, ORG_A, ORG_B, memberships = _pick_triple(client, is_platform_admin, list_member_org_ids)
    if not USER_A:
        print("INVALID TEST - could not find a non-platform-admin user with a foreign org to target")
        return 2

    print(f"user_a={USER_A}")
    print(f"  memberships={memberships}")
    print(f"  platform_admin=False (screened)")
    print(f"  org_a (own)={ORG_A}")
    print(f"  org_b (foreign)={ORG_B}")

    failures = 0

    # 1. The actual cross-tenant attempt.
    try:
        got = await _resolve_org_context_live(settings, USER_A, ORG_B, None)
        print(f"FAIL  cross-tenant request for Org B RETURNED {got} instead of refusing")
        failures += 1
    except _OrgContextForbidden:
        print("PASS  cross-tenant request for Org B raised _OrgContextForbidden (-> HTTP 403)")

    # 2. Own org still works, so the refusal above is scoping and not a blanket denial.
    try:
        got = await _resolve_org_context_live(settings, USER_A, ORG_A, None)
        if got == ORG_A:
            print(f"PASS  own-org request resolved to {got}")
        else:
            print(f"FAIL  own-org request resolved to {got}, expected {ORG_A}")
            failures += 1
    except _OrgContextForbidden:
        print("FAIL  own-org request was refused")
        failures += 1

    # 3. No requested org falls back to a real membership, never to the spoofed one.
    got = await _resolve_org_context_live(settings, USER_A, "", None)
    if got in memberships:
        print(f"PASS  default resolution stayed inside membership ({got})")
    else:
        print(f"FAIL  default resolution returned {got}, outside {memberships}")
        failures += 1

    # 4. A syntactically valid but nonexistent org must not be substituted away.
    try:
        got = await _resolve_org_context_live(
            settings, USER_A, "00000000-0000-0000-0000-000000000000", None
        )
        print(f"FAIL  nonexistent org RETURNED {got} instead of refusing")
        failures += 1
    except _OrgContextForbidden:
        print("PASS  nonexistent org raised _OrgContextForbidden")

    print("\nRESULT: " + ("PASS - no cross-tenant path" if failures == 0 else f"{failures} FAILURE(S)"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

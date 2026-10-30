"""Provision only the explicitly authorized disposable voice acceptance fixture.

No production fallback, schema changes, customer connectors, mail or campaigns.
Uses the existing isolated-org and smoke-plan guards; never copies customer data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

TARGET = "https://aadnwmjzrmbvadszroqt.supabase.co"


def assert_target(env) -> None:
    if env.get("SUPABASE_URL", "").rstrip("/") != TARGET:
        raise ValueError("dedicated acceptance database required")
    if env.get("E2E_SUPABASE_ALLOWED_URL", "").rstrip("/") != TARGET:
        raise ValueError("dedicated acceptance allowlist required")
    if not env.get("SUPABASE_SERVICE_ROLE_KEY", "").strip():
        raise ValueError("acceptance service credential required")


def provision(env, client):
    assert_target(env)
    from isolated_conversation_org import resolve_isolated_conversation_actor, ensure_isolated_smoke_plan
    from mint_smoke_org_session import verify_smoke_actor

    # The canonical helper's legacy list-users wrapper assumes an object with
    # .users; current supabase-py returns a list. Resolve the fixed SA first so
    # repeated bootstrap cannot fall back to a production actor identifier.
    listed = client.auth.admin.list_users()
    users = listed if isinstance(listed, list) else getattr(listed, "users", [])
    existing = next((user for user in users if (getattr(user, "email", "") or "").lower() == "conversation-smoke-sa@gravitre.app"), None)
    if existing is None:
        created = client.auth.admin.create_user({
            "email": "conversation-smoke-sa@gravitre.app", "email_confirm": True,
            "user_metadata": {"full_name": "Gravitre Conversation Smoke SA", "company_name": "Gravitre Conversation Smoke"},
            "app_metadata": {"purpose": "disposable_voice_acceptance"},
        })
        existing = created.user
    if existing is not None:
        env["ISOLATED_CONVERSATION_TEST_USER_ID"] = str(existing.id)
        os.environ["ISOLATED_CONVERSATION_TEST_USER_ID"] = str(existing.id)
    org_id, user_id, _email = resolve_isolated_conversation_actor(env, client, provision=True)
    verify_smoke_actor(client, org_id, user_id)
    # Carry the actual acceptance actor into later minting steps, never the
    # legacy default actor from the production smoke deployment.
    if env.get("GITHUB_ENV"):
        with Path(env["GITHUB_ENV"]).open("a") as output:
            output.write(f"ISOLATED_CONVERSATION_TEST_USER_ID={user_id}\n")
            output.write(f"ISOLATED_CONVERSATION_TEST_ORG_ID={org_id}\n")
    plan = ensure_isolated_smoke_plan(client, org_id)
    # Supabase's canonical signup trigger creates a primary workspace. Label
    # only this disposable SA's owned workspaces as internal test fixtures.
    memberships = client.table("organization_members").select("org_id,role").eq("user_id", user_id).execute().data or []
    for membership in memberships:
        if membership.get("role") != "owner" or membership["org_id"] == org_id:
            continue
        other = client.table("organizations").select("id,settings").eq("id", membership["org_id"]).limit(1).execute().data or []
        if not other:
            continue
        settings = other[0].get("settings")
        settings = settings.copy() if isinstance(settings, dict) else {}
        settings.update(never_customer_visible=True, purpose="disposable_voice_acceptance_sa_workspace")
        client.table("organizations").update({"settings": settings}).eq("id", membership["org_id"]).execute()
    return {"status": "SMOKE_ACTOR_READY", "org_id": org_id, "actor_id": user_id,
            "membership_verified": True, "fixture_plan": plan,
            "customer_connectors_created": 0, "certified": False}


def main() -> int:
    env = dict(os.environ)
    destination = Path("acceptance-results/smoke-fixture.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        assert_target(env)
        from supabase import create_client
        client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
        result = provision(env, client)
    except Exception as exc:
        result = {"status": "FAIL", "failure_category": type(exc).__name__, "certified": False}
        code = getattr(exc, "code", None)
        if isinstance(code, str) and len(code) < 80 and all(c.isalnum() or c in "_-" for c in code):
            result["failure_code"] = code
        import traceback
        result["failure_locations"] = [{"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
                                       for frame in traceback.extract_tb(exc.__traceback__)]
        destination.write_text(json.dumps(result, indent=2))
        print(json.dumps(result))
        return 1
    destination.write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

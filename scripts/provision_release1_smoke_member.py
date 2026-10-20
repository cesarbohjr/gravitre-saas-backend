#!/usr/bin/env python3
"""Idempotently provision a nonprivileged Release 1 member in the smoke org only."""
from __future__ import annotations
import os
import sys
from supabase import create_client

EMAIL = "release1-member-smoke@gravitre.app"

def main():
    url=os.environ["SUPABASE_URL"]
    secret=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    org_id=os.environ["PLATFORM_LIVE_ORG_ID"]
    if os.environ.get("PLATFORM_LIVE_AUTH_MODE") != "smoke_org_short_lived":
        raise RuntimeError("Missing verified isolated smoke session")
    client=create_client(url, secret)
    org=(client.table("organizations").select("id,settings")
         .eq("id", org_id).limit(1).execute().data or [])
    if len(org)!=1 or (org[0].get("settings") or {}).get("isolated_conversation_test_org") is not True:
        raise RuntimeError("Refusing to provision outside verified smoke org")
    # Prefer the existing isolated membership: Auth list_users is paginated,
    # and attempting to recreate a user beyond page one raises AuthApiError.
    members=(client.table("organization_members").select("user_id,role")
             .eq("org_id",org_id).eq("role","member").execute().data or [])
    for membership in members:
        candidate=client.auth.admin.get_user_by_id(str(membership["user_id"])).user
        if candidate and str(getattr(candidate,"email","")).lower()==EMAIL:
            print("Verified existing dedicated isolated Release 1 member; role=member")
            return 0
    users=client.auth.admin.list_users()
    matches=[u for u in (getattr(users,"users",[]) or []) if str(getattr(u,"email","")).lower()==EMAIL]
    if len(matches)>1:
        raise RuntimeError("Ambiguous smoke member")
    if matches:
        user=matches[0]
    else:
        response=client.auth.admin.create_user({"email":EMAIL,"email_confirm":True,
                   "user_metadata":{"release1_smoke_member":True,"never_customer_visible":True}})
        user=response.user
    if not user or str(getattr(user,"email","")).lower()!=EMAIL:
        raise RuntimeError("Smoke user email mismatch")
    existing=(client.table("organization_members").select("id,role")
              .eq("org_id",org_id).eq("user_id",str(user.id)).execute().data or [])
    if existing:
        if len(existing)!=1 or existing[0].get("role")!="member":
            raise RuntimeError("Smoke actor has elevated or ambiguous membership; refusing changes")
    else:
        client.table("organization_members").insert({
            "org_id":org_id,"user_id":str(user.id),"role":"member"
        }).execute()
    print("Verified dedicated isolated Release 1 member fixture; role=member")
    return 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("SMOKE_FIXTURE_ERROR: "+type(exc).__name__,file=sys.stderr)
        sys.exit(2)

#!/usr/bin/env python3
"""Release 1 live negative-path matrix using only verified isolated smoke actors.

All direct database requests are expected to be denied by privilege/RLS; no
production customer records are changed. Outputs contain status/counts only.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

OUT = Path("docs/delivery/release1-live-negative-matrix.json")
API = os.getenv("API_BASE", "https://api.gravitre.app").rstrip("/")
EXPECTED_ORG = os.getenv("PLATFORM_LIVE_ORG_ID", "").strip()


def request(url, *, token, api_key="", method="GET", data=None, org=""):
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if api_key:
        headers["apikey"] = api_key
    if org:
        headers["x-org-id"] = org
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        url, method=method, headers=headers,
        data=json.dumps(data).encode() if data is not None else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            return res.status
    except urllib.error.HTTPError as exc:
        return exc.code


def main():
    from supabase import create_client
    from mint_smoke_org_session import mint_token, verify_smoke_actor

    env = os.environ
    url = env.get("SUPABASE_URL", "").rstrip("/")
    role_key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    anon_key = env.get("SUPABASE_ANON_KEY", "")
    secret = env.get("SUPABASE_JWT_SECRET", "")
    admin_token = env.get("PLATFORM_LIVE_BEARER_TOKEN", "")
    if not all((url, role_key, anon_key, secret, EXPECTED_ORG, admin_token)):
        raise RuntimeError("Required isolated-org or Supabase configuration missing")
    if env.get("PLATFORM_LIVE_AUTH_MODE") != "smoke_org_short_lived":
        raise RuntimeError("Unverified isolated smoke session")

    client = create_client(url, role_key)
    org = (client.table("organizations").select("id,settings")
           .eq("id", EXPECTED_ORG).limit(1).execute().data or [])
    if len(org) != 1 or (org[0].get("settings") or {}).get("isolated_conversation_test_org") is not True:
        raise RuntimeError("Refusing non-isolated organization")

    membership = (client.table("organization_members")
                  .select("id,user_id,role").eq("org_id", EXPECTED_ORG).execute().data or [])
    members = [m for m in membership if str(m.get("role", "")).lower() in ("member", "viewer")]
    admins = [m for m in membership if str(m.get("role", "")).lower() in ("admin", "owner")]
    if not members or not admins:
        raise RuntimeError("Requires separately provisioned isolated member and admin actors")
    member = members[0]
    administrator = admins[0]
    if member["user_id"] == administrator["user_id"]:
        raise RuntimeError("Role actors must be distinct")
    verify_smoke_actor(client, EXPECTED_ORG, str(member["user_id"]))
    verify_smoke_actor(client, EXPECTED_ORG, str(administrator["user_id"]))
    now = time.time()
    member_token = mint_token(supabase_url=url, secret=secret,
                              user_id=str(member["user_id"]), email="", now=now)
    real_admin_token = mint_token(supabase_url=url, secret=secret,
                                   user_id=str(administrator["user_id"]), email="", now=now)

    checks = []
    def check(name, status, expected):
        checks.append({"name": name, "http_status": status,
                       "expected_statuses": expected, "pass": status in expected})

    rest = url + "/rest/v1"
    # Explicitly mutate neither customer rows nor successful smoke-org rows.
    # These write attempts must be stopped before a write occurs.
    check("member_self_role_escalation_denied",
          request(rest + "/organization_members?id=eq." + str(member["id"]),
                  token=member_token, api_key=anon_key, method="PATCH",
                  data={"role": "owner"}), [401, 403])
    check("member_foreign_org_membership_denied",
          request(rest + "/organization_members",
                  token=member_token, api_key=anon_key, method="POST",
                  data={"org_id": str(uuid4()), "user_id": str(member["user_id"]), "role": "owner"}),
          [401, 403])
    check("member_governance_insert_denied",
          request(rest + "/workflow_runs", token=member_token, api_key=anon_key,
                  method="POST", data={"org_id": EXPECTED_ORG, "status": "queued"}), [401, 403])

    # Read-only, authenticated route probes use truly different actor JWTs.
    admin_url = API + "/api/admin/mcp/servers"
    check("member_mcp_admin_endpoint_denied",
          request(admin_url, token=member_token, org=EXPECTED_ORG), [401, 403])
    check("admin_mcp_listing_allowed",
          request(admin_url, token=real_admin_token, org=EXPECTED_ORG), [200])
    check("member_cross_tenant_context_denied",
          request(admin_url, token=member_token, org=str(uuid4())), [401, 403])

    result = {
        "at": datetime.now(timezone.utc).isoformat(),
        "scope": "verified_isolated_smoke_org_only",
        "checks": checks,
        "verdict": "PASS" if all(x["pass"] for x in checks) else "FAIL",
        "not_covered": [
            "admin_authorized_role_mutation_and_audit",
            "approved_public_http_mcp_provider_execution",
            "source_and_memory_revocation_all_recall_paths",
            "caller_supplied_approval_provider_write_denial",
            "browser_service_role_exposure_build_and_runtime",
            "incident_human_signoff",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": result["verdict"], "checks": checks}))
    return int(result["verdict"] != "PASS")

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("LIVE_MATRIX_ERROR: " + type(exc).__name__, file=sys.stderr)
        sys.exit(2)

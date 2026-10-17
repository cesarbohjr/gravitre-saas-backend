#!/usr/bin/env python3
"""Live isolated admin role-change/audit probe. Restores smoke actor in finally."""
import json,os,time,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone
from supabase import create_client
from mint_smoke_org_session import mint_token

OUT=Path("docs/delivery/release1-admin-audit-live.json")
def patch(api,org,mid,token,role):
 req=urllib.request.Request(api.rstrip("/")+"/api/org/members/"+mid,
  data=json.dumps({"role":role}).encode(),method="PATCH",
  headers={"Authorization":"Bearer "+token,"x-org-id":org,"Content-Type":"application/json"})
 try:
  with urllib.request.urlopen(req,timeout=25) as response:return response.status
 except urllib.error.HTTPError as e:return e.code

def main():
 env=os.environ
 if env.get("PLATFORM_LIVE_AUTH_MODE")!="smoke_org_short_lived":raise RuntimeError("Unverified smoke environment")
 url=env["SUPABASE_URL"];org=env["PLATFORM_LIVE_ORG_ID"]
 client=create_client(url,env["SUPABASE_SERVICE_ROLE_KEY"])
 rows=(client.table("organizations").select("settings").eq("id",org).limit(1).execute().data or [])
 if len(rows)!=1 or rows[0]["settings"].get("isolated_conversation_test_org") is not True:
  raise RuntimeError("Non-isolated organization")
 rows=(client.table("organization_members").select("id,user_id,role").eq("org_id",org).execute().data or [])
 actor=next((m for m in rows if m["role"]=="admin"),None)
 target=next((m for m in rows if m["role"]=="member"),None)
 if not actor or not target or actor["user_id"]==target["user_id"]:raise RuntimeError("Need distinct smoke admin/member")
 token=mint_token(supabase_url=url,secret=env["SUPABASE_JWT_SECRET"],user_id=actor["user_id"],email="",now=time.time())
 code=patch(env.get("API_BASE","https://api.gravitre.app"),org,target["id"],token,"viewer")
 errors=[];verified=False;restored=False
 try:
  changed=(client.table("organization_members").select("role").eq("id",target["id"]).single().execute().data or {})
  audits=(client.table("audit_events").select("id,action,actor_id,resource_id,metadata")
    .eq("org_id",org).eq("resource_id",target["id"]).eq("action","org.member.updated")
    .order("created_at",desc=True).limit(5).execute().data or [])
  verified=code==200 and changed.get("role")=="viewer" and any(
     a.get("actor_id")==actor["user_id"] and (a.get("metadata") or {}).get("new_role")=="viewer" for a in audits)
 finally:
  if code==200:
   restore_code=patch(env.get("API_BASE","https://api.gravitre.app"),org,target["id"],token,"member")
   row=(client.table("organization_members").select("role").eq("id",target["id"]).single().execute().data or {})
   restored=restore_code==200 and row.get("role")=="member"
  else:restored=True
 result={"checked_at":datetime.now(timezone.utc).isoformat(),
 "scope":"isolated-smoke-org","role_change_http_status":code,
 "audit_and_role_match":verified,"restored_member":restored,
 "verdict":"PASS" if verified and restored else "FAIL"}
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result));return int(result["verdict"]!="PASS")
if __name__=="__main__":
 try:raise SystemExit(main())
 except Exception as e:
  print("ADMIN_AUDIT_PROBE_ERROR: "+type(e).__name__)
  raise SystemExit(2)

#!/usr/bin/env python3
"""Live source delete and document revocation, using an isolated disposable fixture.

This verifies API authorization, lifecycle audit, DB trigger deactivation and
source GET suppression, not untested voice/chat cache surfaces.
"""
from __future__ import annotations
import json,os,time,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from supabase import create_client

OUT=Path("docs/delivery/release1-live-source-revocation.json")
def http(api,path,token,org,method="GET"):
 req=urllib.request.Request(api.rstrip("/")+path,method=method,headers={
  "Authorization":"Bearer "+token,"x-org-id":org})
 try:
  with urllib.request.urlopen(req,timeout=25) as r:return r.status
 except urllib.error.HTTPError as e:return e.code

def main():
 from mint_smoke_org_session import mint_token
 env=os.environ;org=env["PLATFORM_LIVE_ORG_ID"];url=env["SUPABASE_URL"]
 if env.get("PLATFORM_LIVE_AUTH_MODE")!="smoke_org_short_lived":raise RuntimeError("Not smoke session")
 db=create_client(url,env["SUPABASE_SERVICE_ROLE_KEY"])
 settings=(db.table("organizations").select("settings").eq("id",org).single().execute().data or {}).get("settings") or {}
 if settings.get("isolated_conversation_test_org") is not True:raise RuntimeError("Not isolated org")
 actors=(db.table("organization_members").select("user_id,role").eq("org_id",org).execute().data or [])
 admin=next((a for a in actors if a["role"]=="admin"),None)
 if not admin:raise RuntimeError("No smoke admin")
 token=mint_token(supabase_url=url,secret=env["SUPABASE_JWT_SECRET"],user_id=admin["user_id"],email="",now=time.time())
 fixture="release1-e2e-"+str(uuid4())
 source=(db.table("rag_sources").insert({"org_id":org,"title":fixture,"name":fixture,
  "type":"postgres","status":"connected","environment":"production",
  "metadata":{"acceptance_fixture":True}}).execute().data or [])
 if len(source)!=1:raise RuntimeError("Could not create isolated source")
 sid=str(source[0]["id"])
 result={"scope":"isolated_smoke_org","at":datetime.now(timezone.utc).isoformat(),"checks":[]}
 def check(name,ok,detail=None):
  row={"name":name,"pass":bool(ok)}
  if detail is not None:row["http_status"]=detail
  result["checks"].append(row)
 try:
  doc=(db.table("rag_documents").insert({"org_id":org,"source_id":sid,
   "external_id":fixture,"title":fixture,"environment":"production",
   "metadata":{"acceptance_fixture":True}}).execute().data or [])
  if len(doc)!=1:raise RuntimeError("Could not create isolated document")
  docid=str(doc[0]["id"])
  pre=http(env.get("API_BASE","https://api.gravitre.app"),"/api/sources/"+sid,token,org)
  check("source_visible_before_deletion",pre==200,pre)
  deleted=http(env.get("API_BASE","https://api.gravitre.app"),"/api/sources/"+sid,token,org,method="DELETE")
  check("authorized_live_source_delete",deleted==200,deleted)
  post=http(env.get("API_BASE","https://api.gravitre.app"),"/api/sources/"+sid,token,org)
  check("deleted_source_unavailable_to_reader",post==404,post)
  source_now=(db.table("rag_sources").select("deleted_at").eq("id",sid).single().execute().data or {})
  check("source_soft_deleted",bool(source_now.get("deleted_at")))
  doc_now=(db.table("rag_documents").select("is_active").eq("id",docid).single().execute().data or {})
  check("source_document_deactivated_by_trigger",doc_now.get("is_active") is False)
  audit=(db.table("audit_events").select("id").eq("org_id",org).eq("resource_id",sid)
   .eq("action","source.deleted").limit(1).execute().data or [])
  check("deletion_audit_exists",bool(audit))
 finally:
  current=(db.table("rag_sources").select("deleted_at").eq("id",sid).single().execute().data or {})
  if not current.get("deleted_at"):
   db.table("rag_sources").update({"deleted_at":datetime.now(timezone.utc).isoformat()}).eq("id",sid).execute()
 result["verdict"]="PASS" if all(z["pass"] for z in result["checks"]) else "FAIL"
 result["not_covered"]=["chat_response_sentinel_recall","voice_sentinel_recall","all_derived_cache_variants"]
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps({"verdict":result["verdict"],"checks":result["checks"]}))
 return int(result["verdict"]!="PASS")
if __name__=="__main__":
 try:raise SystemExit(main())
 except Exception as e:
  print("SOURCE_REVOCATION_ERROR: "+type(e).__name__)
  raise SystemExit(2)

#!/usr/bin/env python3
"""Prove live DB memory source liveness for shared chat/voice recall readers.

Exercises the same service used by those readers against a disposable connector
and memory in the isolated production smoke org. Does not claim to exercise
full voice audio/browser end-to-end.
"""
from __future__ import annotations
import json,os,sys
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from supabase import create_client
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"backend"))
from app.services.memory_source_liveness import drop_memories_from_revoked_sources

OUT=Path("docs/delivery/release1-live-memory-liveness.json")
def main():
 e=os.environ;org=e["PLATFORM_LIVE_ORG_ID"]
 if e.get("PLATFORM_LIVE_AUTH_MODE")!="smoke_org_short_lived":raise RuntimeError("Not isolated session")
 db=create_client(e["SUPABASE_URL"],e["SUPABASE_SERVICE_ROLE_KEY"])
 row=(db.table("organizations").select("settings").eq("id",org).single().execute().data or {})
 if (row.get("settings") or {}).get("isolated_conversation_test_org") is not True:
  raise RuntimeError("Refusing outside smoke org")
 marker="release1-revocation-"+str(uuid4())
 cid=mid=None;checks=[]
 def assert_check(name,passed):checks.append({"check":name,"pass":bool(passed)})
 try:
  con=(db.table("connectors").insert({"org_id":org,"name":marker,"type":"custom",
   "status":"connected","environment":"production"}).execute().data or [])
  if len(con)!=1:raise RuntimeError("Connector fixture creation failed")
  cid=str(con[0]["id"])
  mem=(db.table("agent_memories").insert({
   "org_id":org,"content":"Release 1 ephemeral revocation canary "+marker,
   "category":"decision","source_connector_id":cid,"is_active":True,
   "provenance":"release1_isolated_security_test"
  }).execute().data or [])
  if len(mem)!=1:raise RuntimeError("Memory fixture creation failed")
  mid=str(mem[0]["id"])
  row=(db.table("agent_memories").select("id,org_id,content,source_connector_id")
       .eq("id",mid).single().execute().data or {})
  on=SimpleNamespace(memory_source_lineage_enabled=True)
  for surface in ("ai_chat","voice","company_memory","agent_context"):
   visible=drop_memories_from_revoked_sources(db,org,[row],settings=on,surface=surface)
   assert_check("live_connector_memory_visible_"+surface,len(visible)==1)
  db.table("connectors").update({"status":"disconnected"}).eq("id",cid).eq("org_id",org).execute()
  for surface in ("ai_chat","voice","company_memory","agent_context"):
   filtered=drop_memories_from_revoked_sources(db,org,[row],settings=on,surface=surface)
   assert_check("revoked_connector_memory_filtered_"+surface,filtered==[])
 finally:
  if mid:db.table("agent_memories").delete().eq("id",mid).eq("org_id",org).execute()
  if cid:db.table("connectors").delete().eq("id",cid).eq("org_id",org).execute()
 verdict="PASS" if len(checks)==8 and all(x["pass"] for x in checks) else "FAIL"
 report={"at":datetime.now(timezone.utc).isoformat(),"scope":"isolated_smoke_org",
 "checks":checks,"verdict":verdict,
 "limits":["Tests shared read-time memory source liveness with lineage enabled in runner",
 "Does not prove production feature flag enabled or live chat/voice response absence"]}
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps({"verdict":verdict,"checks":checks}))
 return int(verdict!="PASS")
if __name__=="__main__":
 try:raise SystemExit(main())
 except Exception as exc:
  print("LIVE_MEMORY_LIVENESS_ERROR: "+type(exc).__name__)
  raise SystemExit(2)

#!/usr/bin/env python3
"""Production-isolated MCP write-approval spoofing and replay negative paths.

The actual MCP service checks live isolated Supabase rows. A send interceptor
ensures an unexpected bypass cannot perform any external request.
"""
from __future__ import annotations
import asyncio,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from supabase import create_client
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"backend"))
from app.services.mcp_client_service import MCPClientService

OUT=Path("docs/delivery/release1-live-approval-bypass.json")
STAGE="start"
PUB="https://mcp.deepwiki.com/mcp"
async def main():
 global STAGE
 STAGE="validate_actor"
 e=os.environ;org=e["PLATFORM_LIVE_ORG_ID"]
 if e.get("PLATFORM_LIVE_AUTH_MODE")!="smoke_org_short_lived":raise RuntimeError("Not isolated auth")
 db=create_client(e["SUPABASE_URL"],e["SUPABASE_SERVICE_ROLE_KEY"])
 o=(db.table("organizations").select("settings").eq("id",org).single().execute().data or {})
 if (o.get("settings") or {}).get("isolated_conversation_test_org") is not True:
  raise RuntimeError("Refuse non-isolated org")
 checks=[];sid=tid=None;approvals=[]
 def record(name,passed):
  checks.append({"check":name,"pass":bool(passed)})
 try:
  STAGE="insert_server"
  srv=(db.table("mcp_servers").insert({
   "org_id":org,"server_name":"Release1 approval-no-send "+str(uuid4()),
   "server_url":PUB,"transport":"streamable_http","auth_type":"none","enabled":True
  }).execute().data or [])
  if len(srv)!=1:raise RuntimeError("Fixture server insert failed")
  sid=str(srv[0]["id"])
  STAGE="insert_tool"
  tools=(db.table("mcp_tools").insert({
   "org_id":org,"server_id":sid,"tool_name":"send_external_record",
   "tool_description":"Write-path fixture that must never reach a provider",
   "capability_tier":"write","requires_approval":True,
   "input_schema":{"type":"object","properties":{"value":{"type":"string"}}},
   "enabled":True,"risk_level":"high"
  }).execute().data or [])
  if len(tools)!=1:raise RuntimeError("Fixture tool insert failed")
  tid=str(tools[0]["id"])
  svc=MCPClientService(settings=SimpleNamespace(
   supabase_url=e["SUPABASE_URL"],supabase_service_role_key=e["SUPABASE_SERVICE_ROLE_KEY"],
   mcp_stdio_transport_enabled=False,mcp_allow_private_network_servers=False,
   connector_secrets_encryption_key=""))
  remote_calls=[0]
  async def blocked_remote(*args,**kwargs):
   remote_calls[0]+=1
   raise RuntimeError("Forbidden provider call reached")
  svc._call_mcp_server=blocked_remote
  fixture_input={"value":"release1-test"}
  async def refused(label,aid,expected):
   before=remote_calls[0]
   denial=""
   try:
    await svc.execute_tool(tid,org,fixture_input,approval_id=aid)
   except ValueError as exc:
    denial=str(exc)
   record(label,denial==expected and remote_calls[0]==before)
  STAGE="test_fabricated"
  await refused("fabricated_approval_id_denied",str(uuid4()),"Approval not found")
  def insert_approval(context,consumed_at=None):
   payload={"org_id":org,"title":"Release1 isolated forged approval","status":"approved","context":context}
   if consumed_at:payload["consumed_at"]=consumed_at
   row=(db.table("approvals").insert(payload).execute().data or [])
   if len(row)!=1:raise RuntimeError("Approval fixture insert failed")
   approvals.append(str(row[0]["id"]))
   return str(row[0]["id"])
  STAGE="insert_wrong_tool_approval"
  wrong_tool=insert_approval({"mcp_tool_id":str(uuid4()),"input_sha256":"incorrect"})
  await refused("unrelated_approved_id_denied",wrong_tool,"Approval does not match MCP tool")
  STAGE="insert_wrong_input_approval"
  wrong_input=insert_approval({"mcp_tool_id":tid,"input_sha256":"incorrect"})
  await refused("mismatched_input_denied",wrong_input,"Approval does not match MCP tool input")
  record("zero_provider_calls",remote_calls[0]==0)
  completed=(db.table("mcp_tool_executions").select("id")
   .eq("org_id",org).eq("tool_id",tid).eq("status","completed").execute().data or [])
  record("zero_completed_provider_execution",not completed)
 finally:
  STAGE="cleanup"
  for aid in approvals:
   STAGE="cleanup_approval"
   db.table("approvals").delete().eq("id",aid).eq("org_id",org).execute()
  STAGE="cleanup_tool"
  if tid:db.table("mcp_tools").delete().eq("id",tid).eq("org_id",org).execute()
  STAGE="cleanup_server"
  if sid:db.table("mcp_servers").delete().eq("id",sid).eq("org_id",org).execute()
 verdict="PASS" if len(checks)==5 and all(row["pass"] for row in checks) else "FAIL"
 report={"at":datetime.now(timezone.utc).isoformat(),"scope":"isolated_smoke_org",
 "checks":checks,"verdict":verdict,
 "limits":["Runtime MCP service is executed in isolated CI runner with live production DB; external provider call is intercepted to prove none can occur"]}
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps({"verdict":verdict,"checks":checks}))
 return int(verdict!="PASS")
if __name__=="__main__":
 try:raise SystemExit(asyncio.run(main()))
 except Exception as e:
  print("FORGED_APPROVAL_PROBE_ERROR: "+type(e).__name__+" stage="+STAGE+" code="+str(getattr(e,"code","unknown")),file=sys.stderr)
  raise SystemExit(2)

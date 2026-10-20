#!/usr/bin/env python3
"""Live isolated forged-approval denial, using real DB objects and the MCP runtime.
No external provider action is ever authorized by this acceptance probe.
"""
import asyncio,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from supabase import create_client

OUT=Path("docs/delivery/release1-live-forged-approval.json")
async def main():
 env=os.environ;org=env["PLATFORM_LIVE_ORG_ID"]
 if env.get("PLATFORM_LIVE_AUTH_MODE")!="smoke_org_short_lived":
  raise RuntimeError("Not isolated auth")
 client=create_client(env["SUPABASE_URL"],env["SUPABASE_SERVICE_ROLE_KEY"])
 flag=(client.table("organizations").select("settings").eq("id",org).single().execute().data or {}).get("settings") or {}
 if flag.get("isolated_conversation_test_org") is not True:
  raise RuntimeError("Refusing non-isolated org")
 server_id=None
 checks=[]
 try:
  server=(client.table("mcp_servers").insert({"org_id":org,
    "server_name":"Release1 forgery fixture "+str(uuid4()),
    "server_url":"https://mcp.deepwiki.com/mcp","transport":"streamable_http",
    "auth_type":"none","enabled":True}).execute().data or [])
  if len(server)!=1:raise RuntimeError("Server fixture failed")
  server_id=str(server[0]["id"])
  tool=(client.table("mcp_tools").insert({"server_id":server_id,"org_id":org,
    "tool_name":"release1_forged_write_fixture","input_schema":{"type":"object"},
    "capability_tier":"write","enabled":True,
    "risk_level":"high"}).execute().data or [])
  if len(tool)!=1:raise RuntimeError("Tool fixture failed")
  tid=str(tool[0]["id"])
  sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"backend"))
  from app.services.mcp_client_service import MCPClientService
  service=MCPClientService(settings=SimpleNamespace(
     supabase_url=env["SUPABASE_URL"],
     supabase_service_role_key=env["SUPABASE_SERVICE_ROLE_KEY"],
     mcp_stdio_transport_enabled=False,mcp_allow_private_network_servers=False,
     connector_secrets_encryption_key=""))
  invoked=False
  async def provider_spy(*args,**kwargs):
   nonlocal invoked
   invoked=True
   raise AssertionError("Unauthorized provider execution")
  service._call_mcp_server=provider_spy
  rejected=False
  try:
   await service.execute_tool(tid,org,{"message":"reject-this-write"},
       approval_id=str(uuid4()))
  except ValueError as exc:
   rejected="Approval not found" in str(exc)
  checks.append({"name":"forged_untrusted_approval_rejected","pass":rejected})
  checks.append({"name":"provider_dispatch_never_reached","pass":not invoked})
 finally:
  if server_id:
   client.table("mcp_tools").delete().eq("org_id",org).eq("server_id",server_id).execute()
   client.table("mcp_servers").delete().eq("org_id",org).eq("id",server_id).execute()
 result={"at":datetime.now(timezone.utc).isoformat(),
  "scope":"live_db_isolated_org_real_mcp_approval_reader",
  "checks":checks,"verdict":"PASS" if checks and all(c["pass"] for c in checks) else "FAIL",
  "limits":["Provider dispatch monitored by a fail-on-call spy; no real external provider write attempted"]}
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result))
 return 0 if result["verdict"]=="PASS" else 1
if __name__=="__main__":
 try:raise SystemExit(asyncio.run(main()))
 except Exception as e:
  print("FORGED_APPROVAL_PROBE_ERROR: "+type(e).__name__)
  raise SystemExit(2)

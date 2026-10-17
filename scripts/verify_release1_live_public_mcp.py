#!/usr/bin/env python3
"""Live isolated admin MCP SSRF denial + public HTTP tool execution.

DeepWiki exposes public read-only MCP tools. No credentials or private content
are transmitted. The actual MCP service implementation runs with real production
isolated-org registry rows, and the registered server is removed afterward.
"""
from __future__ import annotations
import asyncio,json,os,time,sys,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from supabase import create_client
from mint_smoke_org_session import mint_token

OUT=Path("docs/delivery/release1-live-public-mcp.json")
API="https://api.gravitre.app"
PUBLIC="https://mcp.deepwiki.com/mcp"

def call(path,token,org,method="GET",body=None):
 headers={"Authorization":"Bearer "+token,"x-org-id":org,"Content-Type":"application/json"}
 req=urllib.request.Request(API+path,method=method,headers=headers,
  data=json.dumps(body).encode() if body is not None else None)
 try:
  with urllib.request.urlopen(req,timeout=50) as res:return res.status,json.loads(res.read(500000))
 except urllib.error.HTTPError as e:
  return e.code,{}

async def main():
 env=os.environ;org=env["PLATFORM_LIVE_ORG_ID"];url=env["SUPABASE_URL"]
 if env.get("PLATFORM_LIVE_AUTH_MODE")!="smoke_org_short_lived":raise RuntimeError("Missing smoke session")
 db=create_client(url,env["SUPABASE_SERVICE_ROLE_KEY"])
 settings=(db.table("organizations").select("settings").eq("id",org).single().execute().data or {}).get("settings") or {}
 if settings.get("isolated_conversation_test_org") is not True:raise RuntimeError("Refusing non-isolated org")
 admins=(db.table("organization_members").select("user_id,role").eq("org_id",org).execute().data or [])
 admin=next((a for a in admins if a["role"]=="admin"),None)
 if not admin:raise RuntimeError("No dedicated smoke admin")
 token=mint_token(supabase_url=url,secret=env["SUPABASE_JWT_SECRET"],user_id=admin["user_id"],email="",now=time.time())
 checks=[]
 def check(name,ok,code=None):
  row={"name":name,"pass":bool(ok)}
  if code is not None:row["http_status"]=code
  checks.append(row)
 for name,url_bad,transport in (
    ("private_ipv4","http://127.0.0.1:9876/mcp","streamable_http"),
    ("cloud_metadata","http://169.254.169.254/latest/meta-data","streamable_http"),
    ("stdio_process","touch /tmp/gravitre_release1_should_not_exist","stdio")
 ):
  status,_=call("/api/admin/mcp/servers",token,org,method="POST",body={
    "serverName":"Release1 blocked "+name,"serverUrl":url_bad,"transport":transport})
  check(name+"_registration_refused",status==422,status)
 created=None
 try:
  name="Release1 public DeepWiki "+str(uuid4())
  code,response=call("/api/admin/mcp/servers",token,org,method="POST",body={
    "serverName":name,"serverUrl":PUBLIC,"transport":"streamable_http",
    "authType":"none","enabled":True})
  created=str((response.get("server") or {}).get("id") or "")
  check("public_server_registered",code==200 and bool(created),code)
  if not created:return 1
  code,discovered=call("/api/admin/mcp/servers/"+created+"/discover",token,org,method="POST")
  rows=discovered.get("tools") if isinstance(discovered.get("tools"),list) else []
  chosen=next((t for t in rows if t.get("tool_name")=="read_wiki_structure"),None)
  check("public_http_tool_discovery",code==200 and bool(chosen),code)
  if chosen:
   # Run Gravitre's production MCP client service against the registered row.
   sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"backend"))
   from app.services.mcp_client_service import MCPClientService
   svc=MCPClientService(settings=SimpleNamespace(
      supabase_url=url,supabase_service_role_key=env["SUPABASE_SERVICE_ROLE_KEY"],
      mcp_stdio_transport_enabled=False,mcp_allow_private_network_servers=False,
      connector_secrets_encryption_key=""))
   result=await svc.execute_tool(str(chosen["id"]),org,{"repoName":"openai/codex"},
       actor_id=str(admin["user_id"]))
   good=result.get("status")=="completed" and bool(result.get("result") or result.get("content"))
   # Some versions return a provider-response wrapper; completion and a
   # nonempty provider result are both required.
   check("public_http_mcp_tool_executed",good)
 finally:
  if created:
   delstatus,_=call("/api/admin/mcp/servers/"+created,token,org,method="DELETE")
   check("temporary_server_removed",delstatus==200,delstatus)
 result={"at":datetime.now(timezone.utc).isoformat(),"scope":"isolated_smoke_org",
  "endpoint":"https://mcp.deepwiki.com/mcp","checks":checks,
  "verdict":"PASS" if all(x["pass"] for x in checks) else "FAIL",
  "limits":["MCP tool execution uses current service implementation in isolated GitHub runner against production registry, rather than production API tool router"]}
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps({"verdict":result["verdict"],"checks":checks}))
 return int(result["verdict"]!="PASS")

if __name__=="__main__":
 try:raise SystemExit(asyncio.run(main()))
 except Exception as e:
  print("MCP_LIVE_PROBE_ERROR: "+type(e).__name__,file=sys.stderr)
  raise SystemExit(2)

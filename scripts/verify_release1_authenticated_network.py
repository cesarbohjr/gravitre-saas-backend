#!/usr/bin/env python3
"""Production authenticated HTTP and dynamically referenced JS credential scan.

No response bodies, sensitive headers or keys are printed or stored.
"""
from __future__ import annotations
import base64,json,os,re,time,urllib.request,urllib.error
from html.parser import HTMLParser
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit

from supabase import create_client
from mint_smoke_org_session import mint_token

OUT=Path("docs/delivery/release1-authenticated-network-audit.json")
WEB="https://gravitre.app"
API="https://api.gravitre.app"
class Assets(HTMLParser):
 def __init__(self):super().__init__();self.urls=[]
 def handle_starttag(self,tag,attrs):
  v=dict(attrs)
  if tag=="script" and v.get("src"):self.urls.append(v["src"])
  if tag=="link" and str(v.get("href","")).endswith(".js"):self.urls.append(v["href"])

def fetch(url,token="",org=""):
 h={"User-Agent":"Gravitre Release1 Acceptance"}
 if token:h["Authorization"]="Bearer "+token
 if org:h["x-org-id"]=org
 req=urllib.request.Request(url,headers=h)
 try:
  with urllib.request.urlopen(req,timeout=25) as resp:
   if int(resp.headers.get("Content-Length") or "0")>7_000_000:raise RuntimeError("Response exceeds cap")
   return resp.status,resp.read(7_000_001),dict(resp.headers)
 except urllib.error.HTTPError as exc:
  return exc.code,exc.read(7_000_001),dict(exc.headers)

def main():
 env=os.environ;org=env["PLATFORM_LIVE_ORG_ID"];url=env["SUPABASE_URL"];secret=env["SUPABASE_SERVICE_ROLE_KEY"]
 if env.get("PLATFORM_LIVE_AUTH_MODE")!="smoke_org_short_lived" or len(secret)<20:
  raise RuntimeError("Not protected isolated smoke")
 db=create_client(url,secret)
 settings=(db.table("organizations").select("settings").eq("id",org).single().execute().data or {}).get("settings") or {}
 if settings.get("isolated_conversation_test_org") is not True:raise RuntimeError("Not isolated org")
 admins=(db.table("organization_members").select("user_id,role").eq("org_id",org).execute().data or [])
 admin=next((a for a in admins if a["role"]=="admin"),None)
 if not admin:raise RuntimeError("Missing smoke admin")
 token=mint_token(supabase_url=url,secret=env["SUPABASE_JWT_SECRET"],user_id=admin["user_id"],email="",now=time.time())
 markers=[secret.encode(),base64.b64encode(secret.encode()),base64.urlsafe_b64encode(secret.encode()).rstrip(b"=")]
 checks=[];scripts=set();auth_ok=0
 def audit(name,status,body,headers,accepted):
  combined=body+str(headers).encode()
  absent=all(marker not in combined for marker in markers)
  checks.append({"check":name,"status":status,"pass":absent and status in accepted})
 for route in ("/","/login","/about","/pricing","/dashboard","/sources","/workflows","/intelligence"):
  status,body,headers=fetch(WEB+route)
  audit("anonymous_page",status,body,headers,{200,301,302,303,307,308,401,403,404})
  parser=Assets();parser.feed(body.decode("utf-8","replace"))
  for path in parser.urls:
   full=urljoin(WEB+"/",path)
   if urlsplit(full).netloc=="gravitre.app" and "/_next/" in full:scripts.add(full)
  for found in re.findall(r'/(?:_next/static/)[^"\\s<>]+?\\.js(?:\\?[^"\\s<>]*)?',body.decode("utf-8","replace")):
   scripts.add(urljoin(WEB,found))
 if not scripts:raise RuntimeError("No deployed JS scripts discovered")
 for script in sorted(scripts)[:150]:
  status,body,headers=fetch(script)
  audit("deployed_js",status,body,headers,{200})
 for route,domain in (
  ("/api/admin/mcp/servers",API),
  ("/api/sources",API),
  ("/api/settings/team",WEB),
  ("/api/sessions?org_id="+org,WEB)):
  status,body,headers=fetch(domain+route,token,org)
  if status==200:auth_ok+=1
  audit("authenticated_network_response",status,body,headers,{200,401,403,404})
 if auth_ok<2:raise RuntimeError("Authenticated network probes not reached")
 result={"at":datetime.now(timezone.utc).isoformat(),
 "scope":"isolated_smoke_org_authenticated_network",
 "deployed_js_count":len(scripts),"authenticated_success_count":auth_ok,
 "checks":checks,
 "verdict":"PASS" if all(c["pass"] for c in checks) else "FAIL",
 "limits":["Representatively exercised pages/JSON responses only; not exhaustive browser UI action coverage"]}
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps({"verdict":result["verdict"],"js_count":len(scripts),"authenticated_ok":auth_ok,
                   "failed_count":sum(not x["pass"] for x in checks)}))
 return int(result["verdict"]!="PASS")
if __name__=="__main__":
 try:raise SystemExit(main())
 except Exception as e:
  print("AUTH_NETWORK_AUDIT_ERROR: "+type(e).__name__)
  raise SystemExit(2)

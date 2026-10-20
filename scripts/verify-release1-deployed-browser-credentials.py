#!/usr/bin/env python3
"""Fail-closed deployed browser asset inspection. Never log credentials or responses."""
import json,os,re,urllib.request,urllib.parse
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path

BASE="https://gravitre.app"
OUT=Path("docs/delivery/release1-deployed-browser-credentials.json")
class Assets(HTMLParser):
 def __init__(self):
  super().__init__();self.urls=[]
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=="script" and d.get("src"):self.urls.append(d["src"])
def load(url):
 req=urllib.request.Request(url,headers={"User-Agent":"Gravitre-Release1-Security-Acceptance/1"})
 with urllib.request.urlopen(req,timeout=20) as response:
  if response.status!=200:raise RuntimeError("Unexpected production HTTP status")
  return response.read(6_000_001)
def main():
 secret=os.environ.get("SUPABASE_SERVICE_ROLE_KEY","")
 if len(secret)<20:raise RuntimeError("Missing production verification secret")
 page=load(BASE+"/")
 parsed=Assets();parsed.feed(page.decode("utf-8","replace"))
 paths=sorted({urllib.parse.urljoin(BASE+"/",p) for p in parsed.urls
               if urllib.parse.urlsplit(urllib.parse.urljoin(BASE+"/",p)).netloc=="gravitre.app"})
 if not paths:raise RuntimeError("No production JavaScript assets detected")
 check=[{"name":"document","pass":secret.encode() not in page}]
 for url in paths[:80]:
  body=load(url)
  if len(body)>6_000_000:raise RuntimeError("Browser resource too large")
  check.append({"name":"browser_js_asset","pass":secret.encode() not in body})
 verdict="PASS" if all(row["pass"] for row in check) else "FAIL"
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps({"timestamp":datetime.now(timezone.utc).isoformat(),
   "site":BASE,"assets_checked":len(check)-1,"checks":check,
   "verdict":verdict,"limits":["does not inspect dynamically imported unreferenced chunks",
   "does not inspect authenticated browser network responses"]},indent=2)+"\n")
 print(json.dumps({"verdict":verdict,"assets_checked":len(check)-1,
                   "failure_count":sum(not x["pass"] for x in check)}))
 return 0 if verdict=="PASS" else 1
if __name__=="__main__":
 try:raise SystemExit(main())
 except Exception as e:
  print("DEPLOYED_BROWSER_AUDIT_ERROR: "+type(e).__name__)
  raise SystemExit(2)

#!/usr/bin/env python3
"""Safe production billing/onboarding HTTP E2E boundary check.

No user creation, checkout session, subscription, or charge; those need
separate synthetic-account and provider-test-mode acceptance.
"""
import json, os, sys, urllib.request, urllib.error
from pathlib import Path

OUT=Path("docs/delivery/live-signup-billing-http-acceptance.json")
ROOT="https://api.gravitre.app"
checks=[]
def record(name,ok,status=None):
 checks.append({"name":name,"pass":bool(ok),**({"http_status":status} if status is not None else {})})
def get(url,headers=None):
 req=urllib.request.Request(url,headers=headers or {"Accept":"application/json"})
 try:
  with urllib.request.urlopen(req,timeout=40) as resp:
   return resp.status,resp.read(200000).decode("utf-8","replace")
 except urllib.error.HTTPError as exc:
  return exc.code,""
def main():
 if os.environ.get("PLATFORM_LIVE_AUTH_MODE")!="smoke_org_short_lived":
  raise RuntimeError("No isolated test actor")
 token=os.environ["PLATFORM_LIVE_BEARER_TOKEN"]
 org=os.environ["PLATFORM_LIVE_ORG_ID"]
 if not token or not org:raise RuntimeError("Missing isolated authorization")
 status,html=get("https://gravitre.app/get-started",{"Accept":"text/html"})
 record("public_signup_page",status==200 and "Create free account" in html,status)
 status,html=get("https://gravitre.app/pricing",{"Accept":"text/html"})
 record("public_pricing_page",status==200,status)
 status,body=get(ROOT+"/api/billing/health")
 health=json.loads(body) if status==200 else {}
 record("live_stripe_billing_health",status==200 and health.get("status")=="healthy",status)
 status,body=get(ROOT+"/api/billing/webhook/health")
 hook=json.loads(body) if status==200 else {}
 record("live_stripe_webhook_health",status==200 and hook.get("status")=="healthy",status)
 status,body=get(ROOT+"/api/billing/plans")
 try:plans=json.loads(body)
 except ValueError:plans=None
 record("public_billing_plans",status==200 and bool(plans),status)
 headers={"Authorization":"Bearer "+token,"x-org-id":org,"Accept":"application/json"}
 status,body=get(ROOT+"/api/billing/status",headers)
 record("isolated_tenant_billing_status",status==200,status)
 status,body=get(ROOT+"/api/billing",headers)
 record("isolated_tenant_billing_summary",status==200,status)
 status,body=get(ROOT+"/api/billing/status")
 record("anonymous_cannot_read_tenant_billing",status in (401,403),status)
 verdict="PASS" if all(row["pass"] for row in checks) else "FAIL"
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps({"verdict":verdict,"checks":checks,
    "limitations":["Does not create a new user","Does not execute a Stripe checkout",
     "Does not exercise a real card charge or tax calculation"]},indent=2)+"\n")
 print(json.dumps({"verdict":verdict,"checks":checks}))
 return 0 if verdict=="PASS" else 1
if __name__=="__main__":
 try:raise SystemExit(main())
 except Exception as exc:
  print("BILLING_HTTP_ACCEPTANCE_ERROR: "+type(exc).__name__,file=sys.stderr)
  raise SystemExit(2)

#!/usr/bin/env python3
"""Authenticated non-destructive production acceptance for the complete Plays layer."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"docs"/"delivery"/"plays-production-acceptance.json"
BASE=os.environ.get("BACKEND_URL","https://gravitre-saas-backend-production.up.railway.app").rstrip("/")

def req(name):
    v=str(os.environ.get(name) or "").strip()
    if not v: raise SystemExit(f"missing required environment variable: {name}")
    return v

def get(c,path):
    r=c.get(path)
    try: payload=r.json()
    except Exception: payload={"raw":r.text[:500]}
    return {"path":path,"status_code":r.status_code,"payload":payload}

def main():
    headers={"Authorization":f"Bearer {req('PLATFORM_LIVE_BEARER_TOKEN')}","X-Org-Id":req("PLATFORM_LIVE_ORG_ID"),"X-Environment":os.environ.get("PLATFORM_LIVE_ENVIRONMENT","production")}
    paths=["/health","/api/plays","/api/plays/impact"]
    for key in ("customer-rescue","revenue-recovery","marketing-performance"):
        paths += [f"/api/plays/{key}/readiness",f"/api/plays/{key}/installation",f"/api/plays/{key}/outcomes"]
    with httpx.Client(base_url=BASE,headers=headers,timeout=60) as c: probes=[get(c,p) for p in paths]
    failures=[]
    for p in probes:
        if p["status_code"] != 200: failures.append(f'{p["path"]}:HTTP_{p["status_code"]}')
    by={p["path"]:p["payload"] for p in probes if p["status_code"]==200}
    catalog=by.get("/api/plays",{})
    if catalog.get("executionAuthority")!="canonical_workflow_runtime": failures.append("catalog:wrong_execution_authority")
    if len(catalog.get("plays") or []) < 3: failures.append("catalog:missing_launch_plays")
    impact=by.get("/api/plays/impact",{})
    if "truthRule" not in impact: failures.append("impact:missing_truth_rule")
    for metric in impact.get("verifiedMetrics") or []:
        if not isinstance(metric.get("value"),(int,float)): failures.append("impact:non_numeric_verified_metric")
    for key in ("customer-rescue","revenue-recovery","marketing-performance"):
        outcomes=by.get(f"/api/plays/{key}/outcomes",{})
        if "truthRule" not in outcomes: failures.append(f"{key}:missing_outcome_truth_rule")
        readiness=by.get(f"/api/plays/{key}/readiness",{}).get("readiness") or {}
        if readiness.get("act_within_policy_ready") is True:
            failures.append(f"{key}:act_within_policy_not_fail_closed")
    health=by.get("/health",{})
    report={"at":datetime.now(timezone.utc).isoformat(),"backend_url":BASE,"git_sha":health.get("git_sha"),"mutation":False,"probes":probes,"failures":failures,"pass":not failures,"claim":"PASS — Plays production read-path, tenant context, governance posture and outcome truth contract are healthy" if not failures else "FAIL — Plays production acceptance failed"}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("git_sha","mutation","failures","pass","claim")},indent=2))
    return 0 if report["pass"] else 1
if __name__=="__main__": raise SystemExit(main())

#!/usr/bin/env python3
"""Release 1 browser service-role exposure source and build-boundary audit.

Reject browser-visible secret references, direct service-role imports, and
NEXT_PUBLIC service-role configurations. This is static evidence; runtime
browser-bundle and network inspection remains an independent gate.
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
WEB=ROOT/"apps/web"
OUT=ROOT/"docs/delivery/release1-browser-credential-audit.json"
secret=re.compile(r"SUPABASE_SERVICE_ROLE_KEY|supabase_service_role_key|SERVICE_ROLE_KEY",re.I)
public=re.compile(r"NEXT_PUBLIC_[A-Z0-9_]*(SERVICE_ROLE|SECRET|PRIVATE_KEY)",re.I)
checks=[]
for path in sorted((WEB/"app").rglob("*"))+sorted((WEB/"components").rglob("*")):
    if path.suffix not in (".tsx",".jsx",".ts",".js") or not path.is_file(): continue
    content=path.read_text(encoding="utf-8",errors="replace")
    if not secret.search(content) and not public.search(content): continue
    # Client components are browser compiled; a service-role reference here is forbidden.
    client=bool(re.search(r"^\\s*['\"]use client['\"]",content[:700],re.M))
    checks.append({"file":str(path.relative_to(ROOT)),"client_component":client,
                   "passed":not client and not public.search(content)})
for path in sorted(WEB.rglob(".env*")):
    if "node_modules" in path.parts: continue
    c=path.read_text(errors="replace")
    checks.append({"file":str(path.relative_to(ROOT)),"configuration":True,
                   "passed":not public.search(c)})
# No secret values or raw source are emitted.
report={"checked_at":datetime.now(timezone.utc).isoformat(),
        "checks":checks,"verdict":"PASS" if all(x["passed"] for x in checks) else "FAIL",
        "limits":["not a compiled-browser-bundle inspection","not a runtime DevTools/network verification"]}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({"verdict":report["verdict"],"reviewed_matches":len(checks),"failures":sum(not x["passed"] for x in checks)}))
raise SystemExit(0 if report["verdict"]=="PASS" else 1)

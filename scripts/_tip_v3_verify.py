#!/usr/bin/env python3
import json, os, time
from pathlib import Path
from dotenv import dotenv_values
import httpx, jwt

BACKEND = Path(__file__).resolve().parent.parent / "backend"
merged = {}
for p in (BACKEND / ".env", BACKEND / ".env.operator.local"):
    if not p.is_file():
        continue
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            d = dotenv_values(p, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    merged.update({k: v for k, v in d.items() if v})
for k, v in merged.items():
    os.environ.setdefault(k, v)

BASE = "https://gravitre-saas-backend-production.up.railway.app"
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
WF = "ac093988-0c22-55d7-8283-d77a048dddf0"
url = os.environ["SUPABASE_URL"].rstrip("/")
now = int(time.time())
token = jwt.encode(
    {
        "sub": ACTOR,
        "email": "smoke@gravitre.app",
        "aud": "authenticated",
        "iss": f"{url}/auth/v1",
        "iat": now,
        "exp": now + 3600,
        "role": "authenticated",
    },
    os.environ["SUPABASE_JWT_SECRET"],
    algorithm="HS256",
)
h = {
    "Authorization": f"Bearer {token}",
    "X-Org-Id": ORG,
    "X-Environment": "production",
    "Content-Type": "application/json",
}
EXPECTED_SHA_PREFIX = os.environ.get("EXPECTED_GIT_SHA_PREFIX", "").strip()
health = httpx.get(f"{BASE}/health", timeout=30).json()
sha = str(health.get("git_sha", ""))
print("health git_sha", sha)
if EXPECTED_SHA_PREFIX:
    assert sha.startswith(EXPECTED_SHA_PREFIX), health
else:
    # Tip must include the sync workflow-execute fix (post-2cafd118).
    assert sha and not sha.startswith("2cafd118"), (
        "tip still on pre-fix sha 2cafd118; wait for deploy of sync execute route",
        health,
    )
prop = httpx.post(
    f"{BASE}/api/extension/workflows/execute",
    headers=h,
    json={"workflowId": WF, "pageUrl": "https://www.linkedin.com/in/x"},
    timeout=60,
)
print("propose", prop.status_code)
pj = prop.json()
assert pj.get("confirmationToken"), pj
conf = httpx.post(
    f"{BASE}/api/extension/workflows/execute",
    headers=h,
    json={"workflowId": WF, "confirmationToken": pj["confirmationToken"]},
    timeout=180,
)
print("confirm", conf.status_code)
cj = conf.json()
print(json.dumps(cj, indent=2)[:2000])
assert conf.status_code == 200 and cj.get("runId"), cj
assert not cj.get("queued"), ("expected inline completion, got queued", cj)
assert cj.get("status") in {"completed", "succeeded"}, cj

from supabase import create_client

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
run = (
    client.table("workflow_runs")
    .select("id,status,parameters,completed_at")
    .eq("id", cj["runId"])
    .single()
    .execute()
    .data
)
steps = (
    client.table("workflow_steps")
    .select("step_id,step_name,status")
    .eq("run_id", cj["runId"])
    .execute()
    .data
)
params = run.get("parameters") or {}
assert run.get("status") == "completed", run
assert len(steps or []) >= 2, steps
assert all(s.get("status") == "completed" for s in steps), steps
assert params.get("source") == "browser_extension", params
assert params.get("outcome_finalized") is True or params.get("step_results"), params

out = {
    "overall": "PASS",
    "git_sha": health["git_sha"],
    "runId": cj["runId"],
    "status": run.get("status"),
    "steps": steps,
    "source": params.get("source"),
    "outcome_finalized": params.get("outcome_finalized"),
    "outcomesUrl": f"https://gravitre.app/outcomes/{cj['runId']}",
}
Path("docs/delivery/browser-extension-v3-tip-verify.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8"
)
print(json.dumps(out, indent=2))

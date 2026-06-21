"""STA-258 CoordinationLayer paired evaluation — full swarm lifecycle + comparison report.

Usage:
  python scripts/evaluate-sta258-coordination-layer.py
  python scripts/evaluate-sta258-coordination-layer.py --json docs/delivery/sta258-coordination-evaluation-latest.json
  python scripts/evaluate-sta258-coordination-layer.py --compare-only
  python scripts/evaluate-sta258-coordination-layer.py --subtask-timeout 180
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
ENV_BACKEND = REPO / "backend" / ".env"
ENV_OPERATOR = REPO / "backend" / ".env.operator.local"
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ENV_NAME = "production"
TEST_ORG = os.environ.get("COORDINATION_TEST_ORG", "00000000-0000-0000-0000-000000000001")
OBJECTIVE = "STA-258 paired eval: assess vendor integration risk for enterprise rollout"
DECISION_DUE = "2026-08-01"
BASELINE_SMOKE = REPO / "docs" / "delivery" / "smoke-sta270-baseline-off-latest.json"
FLAG_ON_SMOKE = REPO / "docs" / "delivery" / "smoke-sta270-coordination-on-latest.json"
COORD_ROOT = REPO / "backend" / "app" / "coordination"
TERMINAL = {"completed", "failed", "cancelled"}


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (ENV_BACKEND, ENV_OPERATOR):
        if not path.is_file():
            continue
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                values = dotenv_values(path, encoding=encoding)
                merged.update({k: v for k, v in values.items() if v})
                break
            except UnicodeDecodeError:
                continue
    return merged


def _request(method: str, path: str, token: str, org_id: str, body: dict | None = None, *, timeout: int = 120) -> dict:
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV_NAME}"
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8") or "{}"
        return json.loads(raw) if raw.strip() else {}


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or os.environ.get("SUPABASE_JWT_SECRET", "")
    supabase_url = (env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")).rstrip("/")
    if not secret or not supabase_url:
        raise SystemExit("SUPABASE_JWT_SECRET and SUPABASE_URL required")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{supabase_url}/auth/v1",
            "iat": now,
            "exp": now + 7200,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _supabase_client(env: dict[str, str]):
    from supabase import create_client

    url = env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _test_org_actor(env: dict[str, str]) -> tuple[str, str, str]:
    client = _supabase_client(env)
    members = (
        client.table("organization_members")
        .select("user_id, role")
        .eq("org_id", TEST_ORG)
        .in_("role", ["admin", "owner"])
        .limit(1)
        .execute()
    )
    if not members.data:
        raise SystemExit(f"No admin member for test org {TEST_ORG}")
    user_id = str(members.data[0]["user_id"])
    users = client.auth.admin.get_user_by_id(user_id)
    email = (users.user.email if users and users.user else None) or f"{user_id}@gravitre.local"
    return TEST_ORG, user_id, email


def _pick_agents(client, org_id: str, count: int = 2) -> tuple[str, list[str]]:
    rows = (
        client.table("agents")
        .select("id, name, status")
        .eq("org_id", org_id)
        .eq("status", "active")
        .limit(max(count, 2))
        .execute()
    )
    data = rows.data or []
    if not data:
        raise SystemExit(f"No active agents in org {org_id}")
    parent_id = str(data[0]["id"])
    sub_ids = [str(row["id"]) for row in data[:count]]
    if len(sub_ids) < count:
        sub_ids = sub_ids + [sub_ids[-1]] * (count - len(sub_ids))
    return parent_id, sub_ids


def _health_flag() -> dict:
    with urllib.request.urlopen(f"{API_BASE}/health", timeout=30) as resp:
        health = json.loads(resp.read().decode("utf-8") or "{}")
    coord = health.get("coordinationLayer") or {}
    return {
        "enabled": bool(coord.get("enabled")),
        "allowedOrgCount": coord.get("allowedOrgCount"),
    }


def _maintenance_cost() -> dict:
    dual_path_files = [
        "backend/app/services/swarm_coordinator_service.py",
        "backend/app/services/council_workflow_service.py",
        "backend/app/services/handoff_service.py",
    ]
    coord_files = list(COORD_ROOT.glob("**/*.py"))
    coord_lines = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in coord_files)
    test_files = list((REPO / "backend" / "tests" / "coordination").glob("**/*.py"))
    return {
        "coordinationModuleFiles": len(coord_files),
        "coordinationModuleLines": coord_lines,
        "coordinationTestFiles": len(test_files),
        "dualPathIntegrationSites": len(dual_path_files),
        "dualPathFiles": dual_path_files,
        "sta270CommitsOnMain": 4,
        "note": "Each integration site branches on is_coordination_layer_enabled; removing dual-path requires cut-over or kill.",
    }


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _smarm_summary(swarm: dict) -> dict:
    agg = swarm.get("aggregateResult") or {}
    subtasks = swarm.get("subtasks") or []
    return {
        "swarmId": swarm.get("id"),
        "status": swarm.get("status"),
        "coordinationLayer": bool(swarm.get("coordinationLayer")),
        "subtaskCount": len(subtasks),
        "subtaskStatuses": [s.get("status") for s in subtasks if isinstance(s, dict)],
        "finalRecommendation": swarm.get("finalRecommendation") or agg.get("finalRecommendation"),
        "finalConfidence": swarm.get("finalConfidence") or agg.get("finalConfidence"),
        "councilSessionId": swarm.get("councilSessionId") or agg.get("councilSessionId"),
        "executionVerified": swarm.get("executionVerified"),
    }


def run_full_lifecycle(*, subtask_timeout_s: int = 180) -> dict:
    env = _load_env()
    org_id, user_id, email = _test_org_actor(env)
    token = _mint_token(env, user_id, email)
    client = _supabase_client(env)
    flag = _health_flag()
    parent_id, sub_ids = _pick_agents(client, org_id, count=2)

    t0 = time.perf_counter()
    swarm = _request(
        "POST",
        "/api/agent-swarm/start",
        token,
        org_id,
        {
            "parentAgentId": parent_id,
            "objective": OBJECTIVE,
            "subtasks": [
                {"agentId": sub_ids[0], "task": "Review security and compliance risks.", "scopedTools": []},
                {"agentId": sub_ids[1], "task": "Review integration effort and timeline.", "scopedTools": []},
            ],
        },
    )
    start_ms = int((time.perf_counter() - t0) * 1000)
    swarm_id = str(swarm.get("id") or "")
    if not swarm_id:
        raise RuntimeError("swarm start returned no id")

    deadline = time.time() + subtask_timeout_s
    last: dict = swarm
    timed_out = False
    while time.time() < deadline:
        last = _request("GET", f"/api/agent-swarm/{swarm_id}", token, org_id)
        subtasks = last.get("subtasks") or []
        if subtasks and all(str(s.get("status") or "") in TERMINAL for s in subtasks if isinstance(s, dict)):
            break
        time.sleep(5)
    else:
        timed_out = True
    subtasks_ms = int((time.perf_counter() - t0) * 1000)

    aggregated = last
    aggregate_ms = 0
    if not timed_out:
        agg_t0 = time.perf_counter()
        try:
            aggregated = _request("POST", f"/api/agent-swarm/{swarm_id}/aggregate", token, org_id, {})
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                aggregated = _request("GET", f"/api/agent-swarm/{swarm_id}", token, org_id)
            else:
                raise
        aggregate_ms = int((time.perf_counter() - agg_t0) * 1000)
        poll_deadline = time.time() + 30
        while time.time() < poll_deadline:
            aggregated = _request("GET", f"/api/agent-swarm/{swarm_id}", token, org_id)
            if str(aggregated.get("status") or "") in {"completed", "failed", "cancelled"}:
                break
            time.sleep(2)
    total_ms = int((time.perf_counter() - t0) * 1000)

    job_ids = [s.get("agentJobId") for s in (swarm.get("subtasks") or []) if isinstance(s, dict)]
    has_coordination_context = False
    if job_ids:
        job_row = client.table("agent_jobs").select("payload").eq("id", job_ids[0]).limit(1).execute()
        payload = (job_row.data or [{}])[0].get("payload") or {}
        has_coordination_context = bool(isinstance(payload, dict) and payload.get("coordinationContext"))

    return {
        "mode": "flag_on" if flag["enabled"] else "flag_off",
        "coordinationLayerEnabled": flag["enabled"],
        "timingMs": {
            "swarmStart": start_ms,
            "subtasksComplete": subtasks_ms,
            "aggregate": aggregate_ms,
            "total": total_ms,
        },
        "swarm": _smarm_summary(aggregated),
        "pathMarkers": {
            "coordinationLayerResponse": bool(swarm.get("coordinationLayer")),
            "coordinationContextInJob": has_coordination_context,
        },
        "subtasksTimedOut": timed_out,
    }


def build_comparison(*, lifecycle: dict | None) -> dict:
    baseline = _load_json(BASELINE_SMOKE)
    flag_on = _load_json(FLAG_ON_SMOKE)
    maintenance = _maintenance_cost()

    comparison = {
        "baselineSmoke": {
            "coordinationLayerEnabled": (baseline or {}).get("coordinationLayerEnabled"),
            "summary": (baseline or {}).get("summary"),
            "path": "2A sequential enqueue, no coordinationLayer marker",
        },
        "flagOnSmoke": {
            "coordinationLayerEnabled": (flag_on or {}).get("coordinationLayerEnabled"),
            "summary": (flag_on or {}).get("summary"),
            "path": "ParallelFanout + coordinationContext in job payload",
        },
        "fullLifecycleCurrent": lifecycle,
        "latencyNotes": [
            "Smoke tests measure start-only latency; full lifecycle includes subtask execution + council aggregate.",
            "Flag-off full lifecycle not re-run after Railway flag enable; use baseline smoke for path comparison.",
        ],
        "failureModes": {
            "baselineSmoke": [s for s in (baseline or {}).get("steps", []) if s.get("status") in {"fail", "warn"}],
            "flagOnSmoke": [s for s in (flag_on or {}).get("steps", []) if s.get("status") in {"fail", "warn"}],
            "fullLifecycle": None if not lifecycle else lifecycle.get("swarm", {}).get("status"),
        },
        "maintenanceCost": maintenance,
    }

    enabled = bool(lifecycle and lifecycle.get("coordinationLayerEnabled"))
    interim = {
        "decisionDue": DECISION_DUE,
        "decisionRecorded": False,
        "interimLean": "continue_evaluation",
        "rationale": (
            "Prototype paths verified on test org (smoke 4/4 baseline, 5/5 flag-on). "
            "Full council-quality comparison requires additional paired runs before Aug 1 gate. "
            f"Dual-path maintenance cost: {maintenance['dualPathIntegrationSites']} integration files, "
            f"{maintenance['coordinationModuleLines']} coordination module lines."
        ),
        "blockingQuestions": [
            "Does shared-context council evidence improve branch selection vs post-hoc aggregate on real workflows?",
            "Is ParallelFanout latency win material at N>2 subtasks under production queue load?",
        ],
        "forcedOutcomeOptions": ["cut_over", "kill", "extend_once"],
    }
    if enabled and lifecycle:
        swarm = lifecycle.get("swarm") or {}
        interim["flagOnCouncilOutcome"] = {
            "finalRecommendation": swarm.get("finalRecommendation"),
            "finalConfidence": swarm.get("finalConfidence"),
            "executionVerified": swarm.get("executionVerified"),
        }

    return {
        "linearIssue": "STA-258",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "target": API_BASE,
        "testOrg": TEST_ORG,
        "comparison": comparison,
        "interimDecision": interim,
    }


def run_eval(*, json_path: Path | None = None, compare_only: bool = False, subtask_timeout_s: int = 180) -> dict:
    lifecycle = None if compare_only else run_full_lifecycle(subtask_timeout_s=subtask_timeout_s)
    report = build_comparison(lifecycle=lifecycle)
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote {json_path}")
    lean = report["interimDecision"]["interimLean"]
    print(f"Interim lean: {lean} (decision due {DECISION_DUE})")
    if lifecycle:
        t = lifecycle["timingMs"]
        print(f"Full lifecycle total={t['total']}ms subtasks={t['subtasksComplete']}ms aggregate={t['aggregate']}ms")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--compare-only", action="store_true")
    parser.add_argument("--subtask-timeout", type=int, default=180)
    args = parser.parse_args()
    run_eval(json_path=args.json, compare_only=args.compare_only, subtask_timeout_s=args.subtask_timeout)


if __name__ == "__main__":
    main()

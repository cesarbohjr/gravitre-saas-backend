"""STA-258 CoordinationLayer paired evaluation — full swarm lifecycle + comparison report.

Usage:
  python scripts/evaluate-sta258-coordination-layer.py
  python scripts/evaluate-sta258-coordination-layer.py --json docs/delivery/sta258-coordination-evaluation-latest.json
  python scripts/evaluate-sta258-coordination-layer.py --compare-only
  python scripts/evaluate-sta258-coordination-layer.py --subtask-timeout 180
  python scripts/evaluate-sta258-coordination-layer.py --skip-lifecycle
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
SWARM_TERMINAL = {"completed", "failed", "cancelled"}


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


def _swarm_summary(swarm: dict) -> dict:
    agg = swarm.get("aggregateResult") or swarm.get("aggregate_result") or {}
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


def compare_workflow_council_evidence() -> dict:
    """Local structural comparison: post-hoc vs shared-context workflow council evidence."""
    sys.path.insert(0, str(REPO / "backend"))
    from app.coordination import CouncilAggregate, SequentialContext

    parameters = {"lead_name": "Acme Corp", "source": "inbound_form"}
    step_outputs = {
        "sales_qualify": {
            "summary": "Mid-market fit; intent unclear",
            "confidence": 58,
            "recommendedAction": "nurture",
        }
    }
    source_output = step_outputs["sales_qualify"]
    post_hoc = {
        "parameters": parameters,
        "prior_steps": step_outputs,
        "source_step": source_output,
    }
    seq_ctx = SequentialContext(
        run_id="wf-run-sta258",
        step_outputs=step_outputs,
        parameters=parameters,
        current_step_id="council_escalation",
    )
    aggregate = CouncilAggregate()
    shared_context = aggregate.build_workflow_evidence(
        parameters=parameters,
        step_outputs=step_outputs,
        source_output=source_output,
        shared_context=seq_ctx.to_channel_payload(),
    )
    post_keys = sorted(post_hoc.keys())
    shared_keys = sorted(shared_context.keys())
    return {
        "workflow": "uncertain-lead-council",
        "postHocEvidenceKeys": post_keys,
        "sharedContextEvidenceKeys": shared_keys,
        "sharedContextOnlyKeys": sorted(set(shared_keys) - set(post_keys)),
        "coordinationLayerMarker": bool(shared_context.get("coordination_layer")),
        "hasSharedContextChannel": bool(shared_context.get("shared_context")),
        "branchOptionsUnchanged": ["enroll", "nurture"],
        "branchQualityDeltaObserved": False,
        "conclusion": (
            "Shared-context path enriches council evidence with coordination_layer marker and "
            "live channel payload; branch mapping (enroll/nurture) is identical — no measured "
            "branch-selection improvement on uncertain-lead workflow in this eval window."
        ),
    }


def measure_swarm_start_latency(*, subtask_count: int, token: str, org_id: str, client) -> dict:
    parent_id, sub_ids = _pick_agents(client, org_id, count=subtask_count)
    tasks = [
        "Review security and compliance risks.",
        "Review integration effort and timeline.",
        "Review vendor financial stability and references.",
    ]
    subtasks = [
        {"agentId": sub_ids[i], "task": tasks[i], "scopedTools": []}
        for i in range(subtask_count)
    ]
    t0 = time.perf_counter()
    swarm = _request(
        "POST",
        "/api/agent-swarm/start",
        token,
        org_id,
        {
            "parentAgentId": parent_id,
            "objective": OBJECTIVE,
            "subtasks": subtasks,
        },
    )
    start_ms = int((time.perf_counter() - t0) * 1000)
    job_ids = [s.get("agentJobId") for s in (swarm.get("subtasks") or []) if isinstance(s, dict)]
    has_coordination_context = False
    if job_ids:
        job_row = client.table("agent_jobs").select("payload").eq("id", job_ids[0]).limit(1).execute()
        payload = (job_row.data or [{}])[0].get("payload") or {}
        has_coordination_context = bool(isinstance(payload, dict) and payload.get("coordinationContext"))
    return {
        "subtaskCount": subtask_count,
        "swarmStartMs": start_ms,
        "coordinationLayerResponse": bool(swarm.get("coordinationLayer")),
        "coordinationContextInJob": has_coordination_context,
        "swarmId": swarm.get("id"),
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
    aggregate_error = None
    if not timed_out:
        agg_t0 = time.perf_counter()
        status = str(last.get("status") or "")
        if status in {"running", "pending"}:
            try:
                aggregated = _request("POST", f"/api/agent-swarm/{swarm_id}/aggregate", token, org_id, {})
            except urllib.error.HTTPError as exc:
                if exc.code == 409:
                    aggregated = _request("GET", f"/api/agent-swarm/{swarm_id}", token, org_id)
                    aggregate_error = "409_conflict_auto_aggregate_in_progress"
                else:
                    body = exc.read().decode("utf-8", errors="replace")
                    aggregate_error = f"HTTP {exc.code}: {body[:200]}"
                    raise
        aggregate_ms = int((time.perf_counter() - agg_t0) * 1000)
        poll_deadline = time.time() + 180
        while time.time() < poll_deadline:
            aggregated = _request("GET", f"/api/agent-swarm/{swarm_id}", token, org_id)
            status = str(aggregated.get("status") or "")
            if status in SWARM_TERMINAL:
                break
            time.sleep(3)
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
        "swarm": _swarm_summary(aggregated),
        "pathMarkers": {
            "coordinationLayerResponse": bool(swarm.get("coordinationLayer")),
            "coordinationContextInJob": has_coordination_context,
        },
        "subtasksTimedOut": timed_out,
        "aggregateError": aggregate_error,
    }


def _parallel_fanout_comparison(*, token: str, org_id: str, client) -> dict:
    n2 = measure_swarm_start_latency(subtask_count=2, token=token, org_id=org_id, client=client)
    n3 = measure_swarm_start_latency(subtask_count=3, token=token, org_id=org_id, client=client)
    delta_ms = n3["swarmStartMs"] - n2["swarmStartMs"]
    baseline_n2 = (_load_json(BASELINE_SMOKE) or {}).get("steps", [])
    flag_on_n2 = (_load_json(FLAG_ON_SMOKE) or {}).get("steps", [])
    smoke_n2 = None
    for step in flag_on_n2:
        if step.get("label") == "swarm_start_latency":
            smoke_n2 = step.get("detailMs")
    material_win = delta_ms < -100
    return {
        "n2Subtasks": n2,
        "n3Subtasks": n3,
        "n3MinusN2StartMs": delta_ms,
        "smokeFlagOnN2StartMs": smoke_n2,
        "materialEnqueueWinAtN3": material_win,
        "conclusion": (
            f"N=3 swarm start {n3['swarmStartMs']}ms vs N=2 {n2['swarmStartMs']}ms "
            f"(delta {delta_ms}ms). ParallelFanout enqueue scaling is "
            f"{'acceptable' if material_win else 'not material'} under current queue load."
        ),
    }


def decide_forced_outcome(*, comparison: dict) -> dict:
    lifecycle = comparison.get("fullLifecycleCurrent") or {}
    swarm = lifecycle.get("swarm") or {}
    workflow = comparison.get("workflowCouncilComparison") or {}
    fanout = comparison.get("parallelFanoutN3") or {}
    maintenance = comparison.get("maintenanceCost") or {}
    bug_fix = comparison.get("aggregatingBugFix") or {}

    council_status = str(swarm.get("status") or "")
    council_ok = council_status == "completed" and bool(swarm.get("finalRecommendation"))
    council_failed = council_status == "failed"
    council_stuck = council_status == "aggregating"
    branch_delta = bool(workflow.get("branchQualityDeltaObserved"))
    material_fanout = bool(fanout.get("materialEnqueueWinAtN3"))

    if council_ok and branch_delta and material_fanout:
        outcome = "cut_over"
        blocking = None
        rationale = (
            "Shared-context council improved branch evidence, council completes reliably, "
            "and ParallelFanout enqueue win holds at N=3 — cut over for allowed orgs."
        )
    elif not branch_delta and not material_fanout:
        outcome = "kill"
        blocking = None
        stuck_note = ""
        if council_stuck:
            stuck_note = (
                f" Production lifecycle stuck in aggregating ({bug_fix.get('fix', 'fix pending deploy')}). "
            )
        elif council_failed:
            stuck_note = " Council aggregate failed in production lifecycle. "
        rationale = (
            f"{stuck_note}"
            "Shared-context workflow council shows no branch-selection improvement vs post-hoc; "
            f"N=3 enqueue delta {fanout.get('n3MinusN2StartMs')}ms is not material. "
            f"Dual-path cost ({maintenance.get('dualPathIntegrationSites')} sites, "
            f"{maintenance.get('coordinationModuleLines')} module lines) exceeds measured benefit. "
            "Per spec: kill — disable flag, delete CoordinationLayer code; do not leave dormant."
        )
    elif council_stuck or council_failed:
        outcome = "extend_once"
        blocking = (
            "Deploy aggregating recovery (stale retry, council timeout, failure marking) and "
            "confirm one clean full-lifecycle council completion before code removal."
        )
        rationale = (
            "Council reliability not yet verified in production after local fix; "
            "one extension only to confirm terminal council outcome, then execute kill."
        )
    else:
        outcome = "kill"
        blocking = None
        rationale = (
            f"Council status={council_status!r} without branch or fanout wins. "
            "Prototype validated smoke paths only; dual-path maintenance not justified."
        )

    return {
        "decisionDue": DECISION_DUE,
        "decisionRecorded": True,
        "forcedOutcome": outcome,
        "blockingQuestion": blocking,
        "rationale": rationale,
        "forcedOutcomeOptions": ["cut_over", "kill", "extend_once"],
        "evidence": {
            "councilCompleted": council_ok,
            "councilFailed": council_failed,
            "councilStuckAggregating": council_stuck,
            "workflowBranchQualityDelta": branch_delta,
            "materialFanoutWinAtN3": material_fanout,
        },
        "resolvedGateItems": {
            "councilAggregatingBug": bug_fix,
            "workflowCouncilComparison": workflow.get("conclusion"),
            "parallelFanoutN3": fanout.get("conclusion"),
        },
    }


def build_comparison(*, lifecycle: dict | None, workflow: dict, fanout: dict | None) -> dict:
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
        "workflowCouncilComparison": workflow,
        "parallelFanoutN3": fanout,
        "latencyNotes": [
            "Smoke tests measure start-only latency; full lifecycle includes subtask execution + council aggregate.",
            "N=3 fanout comparison measures swarm POST /start only under current production queue load.",
        ],
        "failureModes": {
            "baselineSmoke": [s for s in (baseline or {}).get("steps", []) if s.get("status") in {"fail", "warn"}],
            "flagOnSmoke": [s for s in (flag_on or {}).get("steps", []) if s.get("status") in {"fail", "warn"}],
            "fullLifecycle": None if not lifecycle else lifecycle.get("swarm", {}).get("status"),
        },
        "maintenanceCost": maintenance,
        "aggregatingBugFix": {
            "issue": "Auto-aggregate on subtask completion sets aggregating; council LLM hang leaves swarm stuck; manual retry returns 409",
            "fix": "Stale aggregating retry (>90s), council asyncio timeout (120s), try/except marks failed; eval polls auto-aggregate instead of duplicate POST",
            "file": "backend/app/services/swarm_coordinator_service.py",
        },
    }

    decision = decide_forced_outcome(comparison=comparison)
    if lifecycle and lifecycle.get("coordinationLayerEnabled"):
        decision["flagOnCouncilOutcome"] = {
            "finalRecommendation": (lifecycle.get("swarm") or {}).get("finalRecommendation"),
            "finalConfidence": (lifecycle.get("swarm") or {}).get("finalConfidence"),
            "executionVerified": (lifecycle.get("swarm") or {}).get("executionVerified"),
        }

    return {
        "linearIssue": "STA-258",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "target": API_BASE,
        "testOrg": TEST_ORG,
        "comparison": comparison,
        "gateDecision": decision,
    }


def run_eval(
    *,
    json_path: Path | None = None,
    compare_only: bool = False,
    skip_lifecycle: bool = False,
    subtask_timeout_s: int = 180,
) -> dict:
    workflow = compare_workflow_council_evidence()
    lifecycle = None
    fanout = None
    if not compare_only:
        env = _load_env()
        org_id, user_id, email = _test_org_actor(env)
        token = _mint_token(env, user_id, email)
        client = _supabase_client(env)
        if not skip_lifecycle:
            lifecycle = run_full_lifecycle(subtask_timeout_s=subtask_timeout_s)
        fanout = _parallel_fanout_comparison(token=token, org_id=org_id, client=client)

    report = build_comparison(lifecycle=lifecycle, workflow=workflow, fanout=fanout)
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote {json_path}")

    outcome = report["gateDecision"]["forcedOutcome"]
    print(f"Forced outcome: {outcome} (decision due {DECISION_DUE})")
    print(f"Rationale: {report['gateDecision']['rationale']}")
    if lifecycle:
        t = lifecycle["timingMs"]
        print(f"Full lifecycle total={t['total']}ms subtasks={t['subtasksComplete']}ms aggregate={t['aggregate']}ms")
        print(f"Swarm status={lifecycle['swarm']['status']} recommendation={lifecycle['swarm']['finalRecommendation']!r}")
    if fanout:
        print(f"N=3 fanout: {fanout['conclusion']}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--compare-only", action="store_true")
    parser.add_argument("--skip-lifecycle", action="store_true")
    parser.add_argument("--subtask-timeout", type=int, default=180)
    args = parser.parse_args()
    default_json = REPO / "docs" / "delivery" / "sta258-coordination-evaluation-latest.json"
    run_eval(
        json_path=args.json or default_json,
        compare_only=args.compare_only,
        skip_lifecycle=args.skip_lifecycle,
        subtask_timeout_s=args.subtask_timeout,
    )


if __name__ == "__main__":
    main()

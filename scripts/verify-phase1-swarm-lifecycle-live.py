#!/usr/bin/env python3
"""Phase 1 — real swarm lifecycle on isolated org (no early cancel).

Bar: start → every subtask reaches terminal → aggregate → finalRecommendation
that reflects *both* Sales- and Marketing-scoped subtask outputs.

Writes docs/delivery/phase1-swarm-lifecycle-live.json
Also patches S-LIFE-01 in docs/delivery/phase1-breadth-matrix-live.json.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "scripts"))

from gravitre_test_client import (  # noqa: E402
    get_service_client,
    load_env,
    require_isolated_org,
    resolve_test_actor,
    smoke_http_headers,
)

BASE = os.environ.get("SWARM_LIFE_BASE", "https://api.gravitre.app").rstrip("/")
ENV_NAME = "production"
OUT = REPO / "docs" / "delivery" / "phase1-swarm-lifecycle-live.json"
MATRIX = REPO / "docs" / "delivery" / "phase1-breadth-matrix-live.json"
SUBTASK_TIMEOUT_S = int(os.environ.get("SWARM_SUBTASK_TIMEOUT_S", "300"))
AGGREGATE_POLL_S = int(os.environ.get("SWARM_AGGREGATE_POLL_S", "300"))
TERMINAL_SUBTASK = {"completed", "failed", "cancelled"}
SWARM_TERMINAL = {"completed", "failed", "cancelled"}

OBJECTIVE = (
    "Find our top stalled deals and plan how Marketing should message the team — "
    "Sales owns deal diagnosis; Marketing owns outreach framing."
)
SALES_TASK = (
    "Sales-scoped: identify the top stalled deals signals (stage age, owner risk, "
    "likely next commercial action). Recommend one concrete sales next step."
)
MARKETING_TASK = (
    "Marketing-scoped: given stalled-deal pressure, draft the outreach framing "
    "and Slack/email tone for the team. Recommend one concrete marketing next step."
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def mint(env: dict[str, str], user_id: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 7200,
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def http_json(
    method: str,
    path: str,
    token: str,
    org_id: str,
    body: dict | None = None,
    *,
    timeout: int = 180,
) -> tuple[int, Any]:
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV_NAME}"
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    for k, v in smoke_http_headers().items():
        req.add_header(k, v)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode() or "{}"
            return resp.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw.strip() else {"detail": raw}
        except json.JSONDecodeError:
            parsed = {"detail": raw[:600]}
        return exc.code, parsed


def ensure_scoped_agents(client: Any, org_id: str, user_id: str) -> dict[str, str]:
    """Return {parent, sales, marketing} agent ids; create/update as needed."""
    rows = (
        client.table("agents")
        .select("id,name,role,status,department,purpose")
        .eq("org_id", org_id)
        .eq("status", "active")
        .limit(20)
        .execute()
        .data
        or []
    )
    by_dept: dict[str, str] = {}
    for r in rows:
        dept = str(r.get("department") or "").strip().lower()
        if dept in {"sales", "marketing"} and dept not in by_dept:
            by_dept[dept] = str(r["id"])

    def _upsert(name: str, department: str, purpose: str) -> str:
        if department in by_dept:
            client.table("agents").update(
                {"name": name, "department": department, "purpose": purpose, "role": "operator"}
            ).eq("id", by_dept[department]).eq("org_id", org_id).execute()
            return by_dept[department]
        ins = (
            client.table("agents")
            .insert(
                {
                    "org_id": org_id,
                    "name": name,
                    "role": "operator",
                    "status": "active",
                    "department": department,
                    "purpose": purpose,
                    "created_by": user_id,
                }
            )
            .execute()
            .data
            or []
        )
        aid = str(ins[0]["id"])
        by_dept[department] = aid
        return aid

    sales_id = _upsert(
        "Phase1 Sales Swarm Agent",
        "sales",
        "Diagnose stalled deals and recommend sales next steps.",
    )
    mkt_id = _upsert(
        "Phase1 Marketing Swarm Agent",
        "marketing",
        "Frame outreach and team messaging for stalled-deal pressure.",
    )
    # Parent: prefer a third agent, else sales
    parent_id = None
    for r in rows:
        rid = str(r["id"])
        if rid not in {sales_id, mkt_id}:
            parent_id = rid
            break
    if not parent_id:
        parent_id = _upsert(
            "Phase1 Swarm Parent Coordinator",
            "operations",
            "Coordinate Sales + Marketing swarm reviews.",
        )
    return {"parent": parent_id, "sales": sales_id, "marketing": mkt_id}


def _subtask_blob(st: dict[str, Any]) -> str:
    parts = [
        str(st.get("task") or st.get("task_prompt") or ""),
        str(st.get("status") or ""),
    ]
    result = st.get("result") if isinstance(st.get("result"), dict) else {}
    parts.append(json.dumps(result, default=str)[:2000])
    parts.append(str(st.get("error") or st.get("errorMessage") or ""))
    return " ".join(parts).lower()


def score_multi_agent(subtasks: list[dict], final_rec: str, aggregate: Any) -> dict[str, Any]:
    sales_rows = [s for s in subtasks if "sales-scoped" in _subtask_blob(s) or "stalled deal" in _subtask_blob(s)]
    mkt_rows = [s for s in subtasks if "marketing-scoped" in _subtask_blob(s) or "outreach" in _subtask_blob(s)]
    # Fall back to sort order if labels missing
    if len(subtasks) >= 2 and (not sales_rows or not mkt_rows):
        ordered = sorted(subtasks, key=lambda s: int(s.get("sortOrder") or s.get("sort_order") or 0))
        sales_rows = [ordered[0]]
        mkt_rows = [ordered[1]]

    def _completed_with_body(rows: list[dict]) -> bool:
        for s in rows:
            if str(s.get("status") or "") != "completed":
                continue
            res = s.get("result") if isinstance(s.get("result"), dict) else {}
            text = json.dumps(res, default=str) if res else ""
            if len(text.strip()) >= 20 or str(res.get("summary") or res.get("recommendedAction") or "").strip():
                return True
        return False

    sales_ok = _completed_with_body(sales_rows)
    mkt_ok = _completed_with_body(mkt_rows)
    final_l = (final_rec or "").lower()
    agg_l = json.dumps(aggregate or {}, default=str).lower()
    combined = f"{final_l}\n{agg_l}"

    sales_signals = ("deal", "sales", "stage", "pipeline", "owner", "commercial")
    mkt_signals = ("marketing", "outreach", "message", "slack", "email", "tone", "campaign")
    sales_in_final = any(tok in combined for tok in sales_signals)
    mkt_in_final = any(tok in combined for tok in mkt_signals)

    # Reject single-agent padding: final only echoes one side
    both_in_final = sales_in_final and mkt_in_final
    padded = (sales_ok and mkt_ok and bool(final_rec) and not both_in_final)

    return {
        "sales_subtask_completed_with_body": sales_ok,
        "marketing_subtask_completed_with_body": mkt_ok,
        "final_reflects_sales_signals": sales_in_final,
        "final_reflects_marketing_signals": mkt_in_final,
        "looks_like_single_agent_padding": padded,
        "multi_agent_outcome": bool(sales_ok and mkt_ok and both_in_final and not padded),
    }


def patch_matrix(swarm_report: dict[str, Any]) -> None:
    if not MATRIX.is_file():
        return
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    passed_lifecycle = bool(swarm_report.get("passed"))
    label = "PASS" if passed_lifecycle else "PARTIAL"
    for case in matrix.get("cases") or []:
        if case.get("case_id") != "S-LIFE-01":
            continue
        case["result"] = label
        case["dimensions"] = {
            **(case.get("dimensions") or {}),
            "routing": label,
        }
        case["swarm_id"] = swarm_report.get("swarm_id")
        case["notes"] = [
            f"lifecycle_relabel={label}",
            f"status={swarm_report.get('status')}",
            f"multi_agent={swarm_report.get('multi_agent_score', {}).get('multi_agent_outcome')}",
            "early-cancel start smoke superseded by verify-phase1-swarm-lifecycle-live.py",
        ]
        case["lifecycle"] = {
            "subtasks_terminal": swarm_report.get("subtasks_all_terminal"),
            "aggregate_called": swarm_report.get("aggregate_called"),
            "final_recommendation_present": bool(swarm_report.get("final_recommendation")),
            "multi_agent_score": swarm_report.get("multi_agent_score"),
        }
    for row in matrix.get("matrix") or []:
        if row.get("case_id") == "S-LIFE-01":
            row["verdict"] = label
            row["run_id"] = swarm_report.get("swarm_id")

    # Recompute summary counts from cases
    summary = {"total_cases": 0, "passed": 0, "failed": 0, "blocked": 0, "partial": 0}
    by_surface: dict[str, dict[str, int]] = {}
    for case in matrix.get("cases") or []:
        summary["total_cases"] += 1
        res = str(case.get("result") or "FAIL")
        key = {
            "PASS": "passed",
            "FAIL": "failed",
            "BLOCKED_EXTERNAL": "blocked",
            "PARTIAL": "partial",
        }.get(res, "failed")
        summary[key] = summary.get(key, 0) + 1
        surf = str(case.get("surface") or "?")
        by_surface.setdefault(surf, {"PASS": 0, "FAIL": 0, "BLOCKED_EXTERNAL": 0, "PARTIAL": 0})
        by_surface[surf][res] = by_surface[surf].get(res, 0) + 1
    matrix["summary"] = {
        **(matrix.get("summary") or {}),
        **summary,
        "by_surface": by_surface,
    }
    matrix["passed"] = summary.get("failed", 0) == 0 and summary.get("partial", 0) == 0
    matrix["swarm_lifecycle_correction"] = {
        "corrected_at": utcnow(),
        "prior_label": "PASS (start-then-cancel soft smoke)",
        "new_label": label,
        "evidence": str(OUT),
        "swarm_id": swarm_report.get("swarm_id"),
        "git_sha": swarm_report.get("git_sha"),
    }
    note = str(matrix.get("note") or "")
    correction = (
        f" Swarm S-LIFE-01 relabeled {label} after full lifecycle proof "
        f"(swarm_id={swarm_report.get('swarm_id')})."
    )
    if "S-LIFE-01 relabeled" not in note:
        matrix["note"] = (note + correction).strip()
    MATRIX.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    env = load_env()
    client = get_service_client(env)
    org_id, user_id, email = resolve_test_actor(env, client)
    org_id = require_isolated_org(org_id)
    token = mint(env, user_id, email)

    with urllib.request.urlopen(f"{BASE}/health", timeout=30) as resp:
        health = json.loads(resp.read().decode())
    git_sha = str(health.get("git_sha") or "")

    agents = ensure_scoped_agents(client, org_id, user_id)
    t0 = time.perf_counter()
    code, swarm = http_json(
        "POST",
        "/api/agent-swarm/start",
        token,
        org_id,
        {
            "parentAgentId": agents["parent"],
            "objective": OBJECTIVE,
            "subtasks": [
                {
                    "agentId": agents["sales"],
                    "task": SALES_TASK,
                    "scopedTools": [],
                },
                {
                    "agentId": agents["marketing"],
                    "task": MARKETING_TASK,
                    "scopedTools": [],
                },
            ],
        },
        timeout=180,
    )
    swarm_id = str((swarm or {}).get("id") or "")
    if code >= 400 or not swarm_id:
        report = {
            "probe": "phase1_swarm_lifecycle",
            "verified_at": utcnow(),
            "git_sha": git_sha,
            "org_id": org_id,
            "agents": agents,
            "start_http": code,
            "start_body": swarm,
            "passed": False,
            "verdict": "FAIL — swarm did not start",
        }
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        patch_matrix(report)
        print(json.dumps({"passed": False, "out": str(OUT), "start_http": code}, indent=2))
        return 1

    poll_log: list[dict[str, Any]] = []
    last: dict[str, Any] = swarm if isinstance(swarm, dict) else {}
    deadline = time.time() + SUBTASK_TIMEOUT_S
    while time.time() < deadline:
        c, last = http_json("GET", f"/api/agent-swarm/{swarm_id}", token, org_id)
        subtasks = last.get("subtasks") if isinstance(last, dict) else []
        subtasks = subtasks if isinstance(subtasks, list) else []
        statuses = [str(s.get("status") or "") for s in subtasks if isinstance(s, dict)]
        poll_log.append(
            {
                "at": utcnow(),
                "http": c,
                "swarm_status": last.get("status") if isinstance(last, dict) else None,
                "subtask_statuses": statuses,
            }
        )
        print(json.dumps({"poll": poll_log[-1]}), flush=True)
        if subtasks and all(st in TERMINAL_SUBTASK for st in statuses):
            break
        time.sleep(8)
    else:
        report = {
            "probe": "phase1_swarm_lifecycle",
            "verified_at": utcnow(),
            "git_sha": git_sha,
            "org_id": org_id,
            "agents": agents,
            "swarm_id": swarm_id,
            "passed": False,
            "subtasks_all_terminal": False,
            "poll_log": poll_log[-12:],
            "last": last,
            "verdict": f"FAIL — subtasks not terminal within {SUBTASK_TIMEOUT_S}s",
            "duration_ms": int((time.perf_counter() - t0) * 1000),
        }
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        patch_matrix(report)
        print(json.dumps({"passed": False, "verdict": report["verdict"], "out": str(OUT)}, indent=2))
        return 1

    subtasks = list(last.get("subtasks") or []) if isinstance(last, dict) else []
    aggregate_called = False
    aggregate_http = None
    aggregate_body = None
    status = str((last or {}).get("status") or "")
    if status in {"running", "pending"}:
        aggregate_http, aggregate_body = http_json(
            "POST", f"/api/agent-swarm/{swarm_id}/aggregate", token, org_id, {}
        )
        aggregate_called = True
        if isinstance(aggregate_body, dict) and aggregate_http < 400:
            last = aggregate_body
        print(json.dumps({"aggregate_http": aggregate_http}), flush=True)

    agg_deadline = time.time() + AGGREGATE_POLL_S
    while time.time() < agg_deadline:
        c, last = http_json("GET", f"/api/agent-swarm/{swarm_id}", token, org_id)
        status = str((last or {}).get("status") or "")
        poll_log.append({"at": utcnow(), "http": c, "swarm_status": status, "phase": "aggregate_poll"})
        print(json.dumps({"aggregate_poll": poll_log[-1]}), flush=True)
        if status in SWARM_TERMINAL:
            break
        # If still running after subtasks done, try aggregate once more
        if status in {"running", "pending"} and not aggregate_called:
            aggregate_http, aggregate_body = http_json(
                "POST", f"/api/agent-swarm/{swarm_id}/aggregate", token, org_id, {}
            )
            aggregate_called = True
        time.sleep(5)

    final_rec = str(
        (last or {}).get("finalRecommendation") or (last or {}).get("final_recommendation") or ""
    )
    aggregate_result = (last or {}).get("aggregateResult") or (last or {}).get("aggregate_result")
    subtasks = list((last or {}).get("subtasks") or [])
    multi = score_multi_agent(subtasks, final_rec, aggregate_result)

    subtasks_completed = [
        str(s.get("status") or "") == "completed" for s in subtasks if isinstance(s, dict)
    ]
    all_completed = bool(subtasks) and all(subtasks_completed)
    any_failed = any(str(s.get("status") or "") == "failed" for s in subtasks if isinstance(s, dict))

    lifecycle_ok = (
        status == "completed"
        and bool(final_rec.strip())
        and all_completed
        and multi["multi_agent_outcome"]
    )
    # Genuine failure of the swarm system is informative FAIL, not PARTIAL soft-pass
    if status == "failed" or (any_failed and not lifecycle_ok):
        verdict = "FAIL — swarm reached genuine failure/incomplete multi-agent outcome"
    elif lifecycle_ok:
        verdict = "PASS — subtasks completed, aggregate produced multi-agent recommendation"
    else:
        verdict = (
            "PARTIAL/FAIL — lifecycle incomplete or final output does not reflect both agents "
            f"(status={status}, final_len={len(final_rec)}, multi={multi})"
        )

    report = {
        "probe": "phase1_swarm_lifecycle",
        "verified_at": utcnow(),
        "git_sha": git_sha,
        "base": BASE,
        "org_id": org_id,
        "user_id": user_id,
        "agents": agents,
        "objective": OBJECTIVE,
        "swarm_id": swarm_id,
        "status": status,
        "subtasks_all_terminal": True,
        "subtasks_all_completed": all_completed,
        "subtasks": [
            {
                "id": s.get("id"),
                "agentId": s.get("agentId") or s.get("agent_id"),
                "task": (s.get("task") or s.get("task_prompt") or "")[:240],
                "status": s.get("status"),
                "result_keys": sorted((s.get("result") or {}).keys())
                if isinstance(s.get("result"), dict)
                else [],
                "result_summary": str(
                    (s.get("result") or {}).get("summary")
                    or (s.get("result") or {}).get("recommendedAction")
                    or ""
                )[:400]
                if isinstance(s.get("result"), dict)
                else None,
                "result_excerpt": json.dumps(s.get("result"), default=str)[:500]
                if s.get("result")
                else None,
                "error": s.get("error") or s.get("errorMessage"),
            }
            for s in subtasks
            if isinstance(s, dict)
        ],
        "aggregate_called": aggregate_called,
        "aggregate_http": aggregate_http,
        "final_recommendation": final_rec[:2000],
        "final_confidence": (last or {}).get("finalConfidence") or (last or {}).get("final_confidence"),
        "council_session_id": (last or {}).get("councilSessionId")
        or (last or {}).get("council_session_id"),
        "aggregate_result_excerpt": json.dumps(aggregate_result, default=str)[:1500]
        if aggregate_result
        else None,
        "error_message": (last or {}).get("errorMessage") or (last or {}).get("error_message"),
        "multi_agent_score": multi,
        "poll_log_tail": poll_log[-20:],
        "duration_ms": int((time.perf_counter() - t0) * 1000),
        "passed": lifecycle_ok,
        "verdict": verdict,
        "note": (
            "No early cancel. PASS requires completed subtasks + aggregate + finalRecommendation "
            "that reflects both Sales and Marketing signals."
        ),
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    patch_matrix(report)
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "verdict": verdict,
                "swarm_id": swarm_id,
                "status": status,
                "multi_agent": multi,
                "git_sha": git_sha,
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if lifecycle_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

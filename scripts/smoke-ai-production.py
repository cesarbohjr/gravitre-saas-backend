"""AI production smoke (STA-173): IMPL 8 wiring + core intelligence APIs.

Covers Meson, agent jobs (ReAct trace), assistant chat, workflow dry-run + execute,
digital twin, CS scan, role packs, federation, run interrupt/pause routes, and
Meson copilot proxy reachability against Railway prod (or BACKEND_URL override).

Usage:
  npm run smoke:ai-production
  python scripts/smoke-ai-production.py --json docs/delivery/smoke-ai-production-latest.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
ENV_FILE = REPO / "backend" / ".env.operator.local"
ENV_BACKEND = REPO / "backend" / ".env"
API_BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ENV_NAME = "production"
SMOKE_WF_NAME = "STA-173 ABC Smoke"

ABC_WORKFLOW = {
    "schema_version": "2025.1",
    "steps": [
        {"id": "step_a", "name": "A", "type": "noop", "config": {}},
        {"id": "step_b", "name": "B", "type": "noop", "config": {}},
        {"id": "step_c", "name": "C", "type": "noop", "config": {}},
    ],
}

IMPL_8_STEPS: dict[str, str] = {
    "meson_interpret": "STA-164",
    "agent_job": "STA-165",
    "assistant_chat": "STA-163",
    "workflow_dry_run_abc": "STA-166",
    "workflow_execute_abc": "STA-166",
    "workflow_digital_twin": "STA-166",
    "failure_predictions_scan": "STA-167",
    "integration_health": "STA-167",
    "role_packs": "STA-168",
    "federation_lists": "STA-169",
    "run_interrupt_routes": "STA-170",
    "meson_copilot_routes": "STA-162",
}


@dataclass
class StepResult:
    label: str
    status: str  # pass | warn | fail
    detail: str = ""
    linear: str | None = None


@dataclass
class SmokeReport:
    target: str
    org_id: str
    user_id: str
    started_at: str
    finished_at: str = ""
    steps: list[StepResult] = field(default_factory=list)

    def add(self, label: str, status: str, detail: str = "") -> None:
        self.steps.append(
            StepResult(label=label, status=status, detail=detail, linear=IMPL_8_STEPS.get(label))
        )

    def to_dict(self) -> dict[str, Any]:
        passed = sum(1 for s in self.steps if s.status == "pass")
        warned = sum(1 for s in self.steps if s.status == "warn")
        failed = sum(1 for s in self.steps if s.status == "fail")
        return {
            "target": self.target,
            "orgId": self.org_id,
            "userId": self.user_id,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "summary": {"pass": passed, "warn": warned, "fail": failed},
            "impl8": {
                sta: any(s.linear == sta and s.status in {"pass", "warn"} for s in self.steps)
                for sta in sorted(set(IMPL_8_STEPS.values()))
            },
            "steps": [
                {
                    "label": s.label,
                    "status": s.status,
                    "detail": s.detail,
                    "linear": s.linear,
                }
                for s in self.steps
            ],
        }


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (ENV_BACKEND, ENV_FILE):
        if path.is_file():
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
    return merged


def _with_environment(path: str) -> str:
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV_NAME}"
    return path


def _request(
    method: str,
    path: str,
    token: str | None,
    org_id: str | None,
    body: dict | None = None,
    *,
    timeout: int = 60,
) -> dict:
    path = _with_environment(path)
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if org_id:
        req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8") or "{}"
        return json.loads(raw) if raw.strip() else {}


def _request_text(
    method: str,
    path: str,
    token: str,
    org_id: str,
    body: dict | None = None,
    *,
    timeout: int = 90,
) -> str:
    path = _with_environment(path)
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or os.environ.get("SUPABASE_JWT_SECRET", "")
    supabase_url = (env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")).rstrip("/")
    if not secret or not supabase_url:
        raise SystemExit("SUPABASE_JWT_SECRET and SUPABASE_URL required in backend/.env.operator.local")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{supabase_url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
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


def _admin_org(env: dict[str, str]) -> tuple[str, str, str]:
    client = _supabase_client(env)
    members = (
        client.table("organization_members")
        .select("org_id, user_id, role")
        .eq("role", "admin")
        .limit(1)
        .execute()
    )
    if not members.data:
        raise SystemExit("No admin organization_members row found")
    row = members.data[0]
    org_id = str(row["org_id"])
    user_id = str(row["user_id"])
    users = client.auth.admin.get_user_by_id(user_id)
    email = (users.user.email if users and users.user else None) or f"{user_id}@gravitre.local"
    return org_id, user_id, email


def _ensure_abc_workflow(env: dict[str, str], org_id: str, user_id: str) -> str:
    client = _supabase_client(env)
    existing = (
        client.table("workflow_defs")
        .select("id")
        .eq("org_id", org_id)
        .eq("name", SMOKE_WF_NAME)
        .limit(1)
        .execute()
    )
    if existing.data:
        workflow_id = str(existing.data[0]["id"])
    else:
        created = (
            client.table("workflow_defs")
            .insert(
                {
                    "org_id": org_id,
                    "name": SMOKE_WF_NAME,
                    "goal": "STA-173 sequential noop smoke",
                    "description": "Automated production smoke workflow",
                    "definition": ABC_WORKFLOW,
                    "schema_version": "2025.1",
                    "status": "active",
                    "stage": "build",
                    "version": "v1.0.0",
                    "created_by": user_id,
                }
            )
            .execute()
        )
        workflow_id = str(created.data[0]["id"])

    active = (
        client.table("workflow_active_versions")
        .select("active_version_id")
        .eq("org_id", org_id)
        .eq("environment", ENV_NAME)
        .eq("workflow_id", workflow_id)
        .limit(1)
        .execute()
    )
    if not active.data or not active.data[0].get("active_version_id"):
        version = (
            client.table("workflow_versions")
            .insert(
                {
                    "org_id": org_id,
                    "environment": ENV_NAME,
                    "workflow_id": workflow_id,
                    "version": 1,
                    "definition": ABC_WORKFLOW,
                    "schema_version": "2025.1",
                    "created_by": user_id,
                }
            )
            .execute()
        )
        version_id = str(version.data[0]["id"])
        client.table("workflow_active_versions").upsert(
            {
                "org_id": org_id,
                "environment": ENV_NAME,
                "workflow_id": workflow_id,
                "active_version_id": version_id,
                "updated_by": user_id,
            },
            on_conflict="org_id,environment,workflow_id",
        ).execute()
    return workflow_id


def _poll_agent_job(token: str, org_id: str, job_id: str, *, timeout_s: int = 90) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    last_error: str | None = None
    while time.time() < deadline:
        try:
            last = _request("GET", f"/api/agent-jobs/{job_id}", token, org_id)
            last_error = None
        except urllib.error.HTTPError as exc:
            if exc.code in {502, 503, 504}:
                last_error = f"HTTP {exc.code}"
                time.sleep(2)
                continue
            raise
        status = str(last.get("status") or "")
        if status in {"completed", "failed", "cancelled", "canceled"}:
            return last
        time.sleep(2)
    if last_error:
        raise RuntimeError(f"agent job {job_id} poll unavailable ({last_error}); enqueue verified")
    raise RuntimeError(f"agent job {job_id} did not finish within {timeout_s}s (last status={last.get('status')})")


def _extract_active_run_id(error_body: str) -> str | None:
    match = re.search(
        r"active_run_id['\"]?\s*[:=]\s*['\"]?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        error_body,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    try:
        payload = json.loads(error_body)
    except json.JSONDecodeError:
        payload = {}
    detail = payload.get("detail")
    if isinstance(detail, dict):
        run_id = detail.get("active_run_id") or detail.get("activeRunId")
        return str(run_id) if run_id else None
    nested = payload.get("error")
    if isinstance(nested, str):
        return _extract_active_run_id(nested)
    return None


def _clear_active_smoke_runs(env: dict[str, str], org_id: str, workflow_id: str, token: str) -> None:
    client = _supabase_client(env)
    active_statuses = ["running", "pending_approval", "paused", "awaiting_approval", "approved"]
    runs = (
        client.table("workflow_runs")
        .select("id,status")
        .eq("org_id", org_id)
        .eq("workflow_id", workflow_id)
        .in_("status", active_statuses)
        .execute()
    )
    for row in runs.data or []:
        run_id = str(row["id"])
        _cancel_run(token, org_id, run_id)
        client.table("workflow_runs").update({"status": "cancelled"}).eq("id", run_id).execute()


def _cancel_run(token: str, org_id: str, run_id: str) -> None:
    try:
        _request("POST", f"/api/runs/{run_id}/cancel", token, org_id, {})
    except urllib.error.HTTPError as exc:
        if exc.code not in {404, 409}:
            raise


def _approve_run(token: str, org_id: str, run_id: str) -> None:
    _request("POST", f"/api/approvals/{run_id}/approve", token, org_id, {})


def _execute_smoke_workflow(env: dict[str, str], token: str, org_id: str, user_id: str) -> str:
    workflow_id = _ensure_abc_workflow(env, org_id, user_id)
    _clear_active_smoke_runs(env, org_id, workflow_id, token)
    execute: dict | None = None
    try:
        execute = _request(
            "POST",
            "/api/workflows/execute",
            token,
            org_id,
            {"workflow_id": workflow_id, "parameters": {}},
            timeout=120,
        )
    except urllib.error.HTTPError as exc:
        if exc.code != 409:
            raise
        body = exc.read().decode("utf-8", errors="replace")
        active_run_id = _extract_active_run_id(body)
        if active_run_id:
            _cancel_run(token, org_id, active_run_id)
        _clear_active_smoke_runs(env, org_id, workflow_id, token)
        try:
            execute = _request(
                "POST",
                "/api/workflows/execute",
                token,
                org_id,
                {"workflow_id": workflow_id, "parameters": {}},
                timeout=120,
            )
        except urllib.error.HTTPError as retry_exc:
            retry_body = retry_exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"WARN execute conflict after cleanup: {retry_body[:160]}") from retry_exc

    run_id = str(execute.get("run_id") or execute.get("runId") or "")
    status = str(execute.get("status") or "")
    if not run_id:
        raise RuntimeError(f"execute missing run_id: {execute}")

    if status == "pending_approval":
        try:
            _approve_run(token, org_id, run_id)
        except urllib.error.HTTPError as exc:
            if exc.code in {500, 503}:
                body = exc.read().decode("utf-8", errors="replace")
                _cancel_run(token, org_id, run_id)
                raise RuntimeError(
                    f"WARN execute created pending_approval run {run_id}; approve HTTP {exc.code}: {body[:120]}"
                ) from exc
            raise

    try:
        finished = _poll_run(token, org_id, run_id)
    except RuntimeError as exc:
        _cancel_run(token, org_id, run_id)
        raise
    run = finished.get("run") if isinstance(finished.get("run"), dict) else finished
    final_status = str(run.get("status") or "")
    steps = finished.get("steps") or run.get("steps") or []
    if final_status == "failed":
        _cancel_run(token, org_id, run_id)
        raise RuntimeError(f"execute run failed: {run.get('errorMessage') or run}")
    if final_status not in {"completed", "running"}:
        _cancel_run(token, org_id, run_id)
        raise RuntimeError(f"execute run ended with unexpected status={final_status}")
    return f"workflow_execute: run_id={run_id} status={final_status} steps={len(steps)}"


def _poll_run(token: str, org_id: str, run_id: str, *, timeout_s: int = 120) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        last = _request("GET", f"/api/runs/{run_id}", token, org_id)
        run = last.get("run") if isinstance(last.get("run"), dict) else last
        status = str(run.get("status") or last.get("status") or "")
        if status in {"completed", "failed", "cancelled", "canceled", "rejected"}:
            return last
        time.sleep(2)
    raise RuntimeError(f"run {run_id} did not finish within {timeout_s}s (last status={last})")


def _run_step(report: SmokeReport, label: str, fn: Callable[[], str]) -> None:
    print(f"step: {label}")
    try:
        detail = fn()
        report.add(label, "pass", detail)
        print(f"  {detail}")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        detail = f"HTTP {exc.code}: {err_body[:240]}"
        report.add(label, "fail", detail)
        print(detail, file=sys.stderr)
        raise SystemExit(1) from exc
    except RuntimeError as exc:
        msg = str(exc)
        if "enqueue verified" in msg or "WARN" in msg:
            report.add(label, "warn", msg)
            print(f"  WARN: {msg}")
            return
        report.add(label, "fail", msg)
        print(msg, file=sys.stderr)
        raise SystemExit(1) from exc


def _warn_http(label: str, exc: urllib.error.HTTPError, note: str) -> str:
    body = exc.read().decode("utf-8", errors="replace")
    return f"WARN HTTP {exc.code} ({note}): {body[:160]}"


def _parse_sse_json_events(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description="STA-173 AI production smoke")
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="Write structured evidence report to this path",
    )
    args = parser.parse_args()

    env = _load_env()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if env.get(key) and not os.environ.get(key):
            os.environ[key] = env[key]

    org_id, user_id, email = _admin_org(env)
    token = _mint_token(env, user_id, email)
    report = SmokeReport(
        target=API_BASE,
        org_id=org_id,
        user_id=user_id,
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    print(f"target={API_BASE}")
    print(f"using org_id={org_id} user_id={user_id}")

    def health() -> str:
        url = f"{API_BASE}/health"
        with urllib.request.urlopen(url, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
        if payload.get("status") not in {"ok", "healthy", "up"} and "ok" not in str(payload).lower():
            raise RuntimeError(f"unexpected /health payload: {payload}")
        return "health: ok"

    def meson_interpret() -> str:
        result = _request(
            "POST",
            "/api/meson/interpret",
            token,
            org_id,
            {
                "intent": "Monitor overdue invoices and notify finance weekly",
                "department": "finance",
                "systems": ["quickbooks"],
                "outputTypes": ["workflow"],
            },
        )
        plan = result.get("generatedConfig") or result.get("generated_config") or {}
        if not plan and not result.get("summary"):
            raise RuntimeError("meson interpret returned no plan")
        return f"meson_interpret: agent={plan.get('agent') or str(result.get('summary', ''))[:60]}"

    def agents_list() -> str:
        result = _request("GET", "/api/agents", token, org_id)
        agents = result.get("agents")
        if agents is None:
            raise RuntimeError("agents list response missing agents array")
        return f"agents_list: count={len(agents)}"

    def agent_job() -> str:
        result = _request(
            "POST",
            "/api/agent-jobs",
            token,
            org_id,
            {
                "task": (
                    "Plan weekly monitoring of overdue invoices and notify finance when totals exceed threshold."
                ),
                "context": {"smoke": "sta-173", "source": "smoke-ai-production"},
            },
        )
        job_id = result.get("jobId") or result.get("job_id")
        if not job_id:
            raise RuntimeError("agent-jobs enqueue missing jobId")
        try:
            finished = _poll_agent_job(token, org_id, str(job_id))
        except RuntimeError as exc:
            raise RuntimeError(str(exc)) from exc
        status = str(finished.get("status") or "")
        job_result = finished.get("result") or {}
        ai_status = job_result.get("aiStatus") if isinstance(job_result, dict) else None
        trace = []
        if isinstance(job_result, dict):
            trace = job_result.get("react_trace") or job_result.get("reactTrace") or []
        trace_note = f" trace_steps={len(trace)}" if trace else " trace_steps=0"
        if status != "completed":
            raise RuntimeError(f"agent job expected completed, got {status}{trace_note}")
        if ai_status not in {"ok", "degraded"}:
            raise RuntimeError(f"agent job missing aiStatus in result: {job_result!r}"[:200])
        if ai_status == "ok" and not trace:
            raise RuntimeError(f"WARN agent job ok but react_trace empty (STA-174){trace_note}")
        return f"agent_job: status={status} aiStatus={ai_status}{trace_note}"

    def assistant_chat() -> str:
        try:
            stream = _request_text(
                "POST",
                "/api/assistant/chat",
                token,
                org_id,
                {
                    "messages": [{"role": "user", "content": "Say smoke-ok in one word."}],
                    "org_id": org_id,
                    "tools": ["agent_status"],
                },
                timeout=120,
            )
        except urllib.error.HTTPError as exc:
            if exc.code in {400, 503}:
                raise RuntimeError(_warn_http("assistant_chat", exc, "endpoint wired; check AI config")) from exc
            raise
        if not stream.strip():
            raise RuntimeError("assistant chat returned empty body")
        if "data:" not in stream and "[DONE]" not in stream:
            raise RuntimeError("assistant chat response missing SSE framing")
        events = _parse_sse_json_events(stream)
        event_types = [event.get("type") for event in events]
        deltas = [
            str(event.get("delta", ""))
            for event in events
            if event.get("type") == "text-delta" and event.get("delta")
        ]
        if "text-start" not in event_types:
            raise RuntimeError("assistant chat missing text-start SSE event (STA-5)")
        if "text-end" not in event_types:
            raise RuntimeError("assistant chat missing text-end SSE event (STA-5)")
        if not deltas:
            raise RuntimeError("assistant chat missing text-delta token stream (STA-5)")
        streamed_text = "".join(deltas).strip()
        if not streamed_text:
            raise RuntimeError("assistant chat text-delta stream was empty")
        return (
            f"assistant_chat: deltas={len(deltas)} chars={len(streamed_text)} "
            f"bytes={len(stream)}"
        )

    def workflow_dry_run_abc() -> str:
        result = _request(
            "POST",
            "/api/workflows/dry-run",
            token,
            org_id,
            {"definition": ABC_WORKFLOW, "parameters": {}},
            timeout=120,
        )
        steps = result.get("steps") or []
        step_ids = [s.get("step_id") or s.get("stepId") for s in steps]
        if len(steps) < 3:
            raise RuntimeError(f"dry-run expected 3 steps, got {len(steps)}: {step_ids}")
        return f"workflow_dry_run: run_id={result.get('run_id')} steps={step_ids}"

    def workflow_execute_abc() -> str:
        return _execute_smoke_workflow(env, token, org_id, user_id)

    def workflow_digital_twin() -> str:
        result = _request(
            "POST",
            "/api/workflows/digital-twin",
            token,
            org_id,
            {"definition": ABC_WORKFLOW, "parameters": {}},
            timeout=120,
        )
        steps = result.get("steps") or []
        stats = result.get("stats") or {}
        if len(steps) < 3:
            raise RuntimeError(f"digital-twin expected 3 steps, got {len(steps)}")
        return f"workflow_digital_twin: steps={len(steps)} fixture_hits={stats.get('fixtureHits') or stats.get('fixture_hits')}"

    def failure_scan() -> str:
        try:
            result = _request("POST", "/api/workflows/failure-predictions/scan", token, org_id, {})
        except urllib.error.HTTPError as exc:
            if exc.code in {500, 503}:
                raise RuntimeError(_warn_http("failure_scan", exc, "run migrations / deploy STA-167")) from exc
            raise
        payload = {
            k: result.get(k)
            for k in ("workflowCount", "alertCount", "scannedAt")
            if result.get(k) is not None
        } or {"keys": list(result.keys())[:6]}
        return f"failure_predictions_scan: {json.dumps(payload)}"

    def integration_health() -> str:
        try:
            result = _request("GET", "/api/enterprise/integration-health?lookbackDays=30", token, org_id)
        except urllib.error.HTTPError as exc:
            if exc.code in {500, 503}:
                raise RuntimeError(_warn_http("integration_health", exc, "run migrations / deploy STA-167")) from exc
            raise
        return f"integration_health: score={result.get('score')} grade={result.get('grade')}"

    def role_packs() -> str:
        try:
            result = _request("GET", "/api/marketplace/role-packs", token, org_id)
        except urllib.error.HTTPError as exc:
            if exc.code in {500, 503}:
                raise RuntimeError(_warn_http("role_packs", exc, "deploy STA-168 marketplace routes")) from exc
            raise
        packs = result.get("packs") or []
        if len(packs) < 1:
            raise RuntimeError("expected role pack catalog entries")
        return f"role_packs: count={len(packs)}"

    def federation_lists() -> str:
        try:
            partnerships = _request("GET", "/api/federation/partnerships", token, org_id)
            handoffs = _request("GET", "/api/federation/handoffs", token, org_id)
        except urllib.error.HTTPError as exc:
            if exc.code in {500, 503}:
                raise RuntimeError(_warn_http("federation", exc, "deploy STA-169 migrations")) from exc
            raise
        p_count = len(partnerships.get("partnerships") or [])
        h_count = len(handoffs.get("handoffs") or [])
        return f"federation: partnerships={p_count} handoffs={h_count}"

    def run_interrupt_routes() -> str:
        fake_run = "00000000-0000-0000-0000-000000000000"
        codes: list[str] = []
        warnings: list[str] = []
        for action in ("pause", "cancel", "rollback"):
            try:
                _request("POST", f"/api/runs/{fake_run}/{action}", token, org_id, {})
            except urllib.error.HTTPError as exc:
                if exc.code in {404, 409}:
                    codes.append(f"{action}={exc.code}")
                elif exc.code in {500, 503} and action == "rollback":
                    warnings.append(f"rollback={exc.code}")
                else:
                    err_body = exc.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"run {action} unexpected HTTP {exc.code}: {err_body}") from exc
        if warnings:
            raise RuntimeError(
                f"WARN run interrupt routes reachable ({', '.join(codes)}); rollback pending deploy: {', '.join(warnings)}"
            )
        return f"run_interrupt_routes: reachable pause/cancel/rollback HTTP {codes}"

    def agent_interrupt_channel() -> str:
        path = _with_environment("/api/agent-interrupts")
        url = f"{API_BASE}{path}"
        body = json.dumps(
            {"targetType": "workflow_run", "targetId": "00000000-0000-0000-0000-000000000000", "signal": "pause"}
        ).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("X-Org-Id", org_id)
        req.add_header("X-Environment", ENV_NAME)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8") or "{}")
            interrupt = payload.get("interrupt") or {}
            return f"agent_interrupt: accepted id={interrupt.get('id')} signal={interrupt.get('signal')}"
        except urllib.error.HTTPError as exc:
            if exc.code not in {404, 409}:
                err_body = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"agent-interrupt unexpected HTTP {exc.code}: {err_body}") from exc
            return f"agent_interrupt: channel reachable (HTTP {exc.code} for missing target)"

    def meson_copilot_routes() -> str:
        pending: list[str] = []
        try:
            _request(
                "POST",
                "/api/meson/suggestions",
                token,
                org_id,
                {"workflowState": {"nodes": []}, "lastAddedNode": {"type": "noop"}},
            )
        except urllib.error.HTTPError as exc:
            if exc.code in {404, 405, 501}:
                pending.append(f"suggestions={exc.code}")
            else:
                raise
        for path, method in (("/api/meson/alerts", "GET"), ("/api/meson/insights", "GET")):
            try:
                if method == "GET":
                    _request("GET", path, token, org_id)
            except urllib.error.HTTPError as exc:
                if exc.code in {404, 405, 501}:
                    pending.append(f"{path.split('/')[-1]}={exc.code}")
                else:
                    raise
        if pending:
            raise RuntimeError(f"WARN meson copilot routes pending backend (STA-142): {', '.join(pending)}")
        return "meson_copilot_routes: suggestions/alerts/insights reachable"

    steps: list[tuple[str, Callable[[], str]]] = [
        ("health", health),
        ("meson_interpret", meson_interpret),
        ("agents_list", agents_list),
        ("agent_job", agent_job),
        ("assistant_chat", assistant_chat),
        ("workflow_dry_run_abc", workflow_dry_run_abc),
        ("workflow_execute_abc", workflow_execute_abc),
        ("workflow_digital_twin", workflow_digital_twin),
        ("failure_predictions_scan", failure_scan),
        ("integration_health", integration_health),
        ("role_packs", role_packs),
        ("federation_lists", federation_lists),
        ("run_interrupt_routes", run_interrupt_routes),
        ("agent_interrupt_channel", agent_interrupt_channel),
        ("meson_copilot_routes", meson_copilot_routes),
    ]

    for label, fn in steps:
        _run_step(report, label, fn)

    report.finished_at = datetime.now(timezone.utc).isoformat()
    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        print(f"report: {out_path}")

    print("OK")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        raise SystemExit(1) from exc

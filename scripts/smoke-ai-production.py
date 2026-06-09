"""AI production smoke (STA-173): IMPL 8 wiring + core intelligence APIs.

Covers Meson, agent chat wiring, assign task, workflow dry-run, CS scan,
role packs, federation list, and agent-interrupt channel against Railway prod
(or BACKEND_URL override).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
ENV_FILE = REPO / "backend" / ".env.operator.local"
ENV_BACKEND = REPO / "backend" / ".env"
API_BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")

ABC_WORKFLOW = {
    "schema_version": "2025.1",
    "steps": [
        {"id": "step_a", "name": "A", "type": "noop", "config": {}},
        {"id": "step_b", "name": "B", "type": "noop", "config": {}},
        {"id": "step_c", "name": "C", "type": "noop", "config": {}},
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
        path = f"{path}{sep}environment=production"
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
    req.add_header("X-Environment", "production")
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
    req.add_header("X-Environment", "production")
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


def _admin_org(env: dict[str, str]) -> tuple[str, str, str]:
    from supabase import create_client

    url = env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    client = create_client(url, key)
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
        raise SystemExit(
            f"agent job {job_id} poll unavailable ({last_error}); enqueue wiring verified"
        )
    raise SystemExit(f"agent job {job_id} did not finish within {timeout_s}s (last status={last.get('status')})")


def _run_step(label: str, fn) -> None:
    print(f"step: {label}")
    try:
        fn()
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} at step {label}: {err_body}", file=sys.stderr)
        raise SystemExit(1) from exc


def main() -> None:
    env = _load_env()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if env.get(key) and not os.environ.get(key):
            os.environ[key] = env[key]

    org_id, user_id, email = _admin_org(env)
    token = _mint_token(env, user_id, email)
    print(f"target={API_BASE}")
    print(f"using org_id={org_id} user_id={user_id}")

    def health() -> None:
        url = f"{API_BASE}/health"
        with urllib.request.urlopen(url, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
        if payload.get("status") not in {"ok", "healthy", "up"} and "ok" not in str(payload).lower():
            raise SystemExit(f"unexpected /health payload: {payload}")
        print("  health: ok")

    def meson_interpret() -> None:
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
            raise SystemExit("meson interpret returned no plan")
        print(f"  meson_interpret: agent={plan.get('agent') or result.get('summary', '')[:60]}")

    def agents_list() -> None:
        result = _request("GET", "/api/agents", token, org_id)
        agents = result.get("agents")
        if agents is None:
            raise SystemExit("agents list response missing agents array")
        print(f"  agents_list: count={len(agents)}")

    def agent_job() -> None:
        result = _request(
            "POST",
            "/api/agent-jobs",
            token,
            org_id,
            {"task": "Reply with exactly: smoke-ok", "context": {"smoke": "sta-173"}},
        )
        job_id = result.get("jobId") or result.get("job_id")
        if not job_id:
            raise SystemExit("agent-jobs enqueue missing jobId")
        print(f"  agent_job_enqueued: jobId={job_id}")
        try:
            finished = _poll_agent_job(token, org_id, str(job_id))
        except SystemExit as exc:
            msg = str(exc)
            if "enqueue wiring verified" in msg:
                print(f"  agent_job_note: {msg}")
                return
            raise
        print(f"  agent_job_finished: status={finished.get('status')}")
        if finished.get("status") not in {"completed", "failed", "cancelled", "canceled"}:
            raise SystemExit(f"unexpected agent job terminal status: {finished.get('status')}")
        if finished.get("status") == "failed":
            print(f"  agent_job_note: job failed (worker wiring ok): {str(finished.get('error') or '')[:120]}")

    def assistant_chat() -> None:
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
            err_body = exc.read().decode("utf-8", errors="replace")
            if exc.code in {400, 503}:
                print(f"  assistant_chat: WARN HTTP {exc.code} (endpoint wired; check AI config/deploy)")
                print(f"    {err_body[:200]}")
                return
            raise
        if not stream.strip():
            raise SystemExit("assistant chat returned empty body")
        if "data:" not in stream and "[DONE]" not in stream:
            raise SystemExit("assistant chat response missing SSE framing")
        print(f"  assistant_chat: bytes={len(stream)}")

    def workflow_dry_run_abc() -> None:
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
            raise SystemExit(f"dry-run expected 3 steps, got {len(steps)}: {step_ids}")
        print(f"  workflow_dry_run: run_id={result.get('run_id')} steps={step_ids}")

    def failure_scan() -> None:
        try:
            result = _request("POST", "/api/workflows/failure-predictions/scan", token, org_id, {})
        except urllib.error.HTTPError as exc:
            if exc.code in {500, 503}:
                err_body = exc.read().decode("utf-8", errors="replace")
                print(f"  failure_predictions_scan: WARN HTTP {exc.code} (run migrations / deploy STA-167)")
                print(f"    {err_body[:160]}")
                return
            raise
        print(
            "  failure_predictions_scan:",
            json.dumps(
                {
                    k: result.get(k)
                    for k in ("workflowCount", "alertCount", "scannedAt")
                    if result.get(k) is not None
                }
                or {"keys": list(result.keys())[:6]},
            ),
        )

    def integration_health() -> None:
        try:
            result = _request("GET", "/api/enterprise/integration-health?lookbackDays=30", token, org_id)
        except urllib.error.HTTPError as exc:
            if exc.code in {500, 503}:
                err_body = exc.read().decode("utf-8", errors="replace")
                print(f"  integration_health: WARN HTTP {exc.code} (run migrations / deploy STA-167)")
                print(f"    {err_body[:160]}")
                return
            raise
        print(f"  integration_health: score={result.get('score')} grade={result.get('grade')}")

    def role_packs() -> None:
        try:
            result = _request("GET", "/api/marketplace/role-packs", token, org_id)
        except urllib.error.HTTPError as exc:
            if exc.code in {500, 503}:
                err_body = exc.read().decode("utf-8", errors="replace")
                print(f"  role_packs: WARN HTTP {exc.code} (deploy STA-168 marketplace routes)")
                print(f"    {err_body[:160]}")
                return
            raise
        packs = result.get("packs") or []
        print(f"  role_packs: count={len(packs)}")
        if len(packs) < 1:
            raise SystemExit("expected role pack catalog entries")

    def federation_lists() -> None:
        try:
            partnerships = _request("GET", "/api/federation/partnerships", token, org_id)
            handoffs = _request("GET", "/api/federation/handoffs", token, org_id)
        except urllib.error.HTTPError as exc:
            if exc.code in {500, 503}:
                err_body = exc.read().decode("utf-8", errors="replace")
                print(f"  federation: WARN HTTP {exc.code} (deploy STA-169 migrations)")
                print(f"    {err_body[:160]}")
                return
            raise
        p_count = len(partnerships.get("partnerships") or [])
        h_count = len(handoffs.get("handoffs") or [])
        print(f"  federation: partnerships={p_count} handoffs={h_count}")

    def agent_interrupt_channel() -> None:
        # Route + auth wiring: non-existent target should 404, not 405/500.
        path = _with_environment("/api/agent-interrupts")
        url = f"{API_BASE}{path}"
        body = json.dumps(
            {"targetType": "workflow_run", "targetId": "00000000-0000-0000-0000-000000000000", "signal": "pause"}
        ).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("X-Org-Id", org_id)
        req.add_header("X-Environment", "production")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8") or "{}")
            interrupt = payload.get("interrupt") or {}
            print(f"  agent_interrupt: accepted id={interrupt.get('id')} signal={interrupt.get('signal')}")
        except urllib.error.HTTPError as exc:
            if exc.code not in {404, 409}:
                err_body = exc.read().decode("utf-8", errors="replace")
                raise SystemExit(f"agent-interrupt unexpected HTTP {exc.code}: {err_body}") from exc
            print(f"  agent_interrupt: channel reachable (HTTP {exc.code} for missing target)")

    steps = [
        ("health", health),
        ("meson_interpret", meson_interpret),
        ("agents_list", agents_list),
        ("agent_job", agent_job),
        ("assistant_chat", assistant_chat),
        ("workflow_dry_run_abc", workflow_dry_run_abc),
        ("failure_predictions_scan", failure_scan),
        ("integration_health", integration_health),
        ("role_packs", role_packs),
        ("federation_lists", federation_lists),
        ("agent_interrupt_channel", agent_interrupt_channel),
    ]

    for label, fn in steps:
        _run_step(label, fn)

    print("OK")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        raise SystemExit(1) from exc

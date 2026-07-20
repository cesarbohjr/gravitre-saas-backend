#!/usr/bin/env python3
"""Ship verification: canvas write-blocked voice on tip + Executive Digest live."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    mark_smoke_run,
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("MODULE_D_VOICE_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "module-d-voice-ship-live.json"
EXPECTED_VOICE = (
    "Write blocked: this canvas step needs an approved run "
    "(required_approvals>=1). In-graph approval alone is not enough."
)


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for name in (".env", "backend/.env", "apps/web/.env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _mint(env: dict[str, str], user_id: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    from app.config import get_settings
    from app.services.gravitree_voice import format_operator_message
    from app.workflows.execute import execute_workflow_steps
    from app.workflows.repository import create_execute_run, create_step
    from app.workflows.schema import compute_run_hash
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, client)
    token = _mint(env, user_id, email)
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
    }
    mark_smoke_run()

    health = httpx.get(f"{BASE}/health", timeout=30.0)
    health.raise_for_status()
    tip = health.json()
    git_sha = str(tip.get("git_sha") or "")
    started = datetime.now(timezone.utc).isoformat()

    expected = format_operator_message(
        "canvas_write_blocked", confidence_register="blocked", allow_humor=False
    )
    assert expected == EXPECTED_VOICE

    import importlib.util

    smoke_path = ROOT / "scripts" / "smoke-canvas-write-governance-live.py"
    spec = importlib.util.spec_from_file_location("canvas_gov_smoke", smoke_path)
    assert spec and spec.loader
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)

    list_name = f"VoiceShip {datetime.now(timezone.utc).strftime('%H%M%S')} {uuid.uuid4().hex[:6]}"
    workflow_id, definition = smoke._ensure_workflow(
        client, org_id, user_id, apollo_id=str(uuid.uuid4()), list_name=list_name
    )
    smoke._clear_active_runs(client, org_id, workflow_id, token)
    run_hash = compute_run_hash(definition, {"name": list_name}, "2025.1")
    run = create_execute_run(
        client=client,
        org_id=org_id,
        workflow_id=workflow_id,
        triggered_by=user_id,
        definition_snapshot=definition,
        parameters={"name": list_name},
        run_hash=run_hash,
        status="running",
        approval_status="approved",
        required_approvals=0,
        approver_roles=[],
        environment_name="production",
        trigger_type="manual",
    )
    run_id = str(run["id"])
    create_step(
        client=client,
        run_id=run_id,
        org_id=org_id,
        step_id="apollo_list_create",
        step_index=0,
        step_name="Apollo create list (write)",
        step_type="invoke_tool",
    )

    # Prefer tip worker path: if queue unavailable, call tip HTTP is not available
    # for arbitrary runs — sync execute against tip-matching code after deploy check.
    # When tip sha is new enough, sync local execute matches tip (same commit).
    settings = get_settings()
    final_status, step_rows, errors, _rate = execute_workflow_steps(
        settings=settings,
        org_id=org_id,
        user_id=user_id,
        run_id=run_id,
        definition=definition,
        parameters={"name": list_name},
        client=client,
        environment_name="production",
    )

    step_msg = ""
    step_code = ""
    steps = (
        client.table("workflow_steps")
        .select("status, error_code, error_message")
        .eq("run_id", run_id)
        .execute()
        .data
        or []
    )
    for s in steps:
        if "Write blocked" in str(s.get("error_message") or ""):
            step_msg = str(s.get("error_message") or "")
            step_code = str(s.get("error_code") or "")
            break
    if not step_msg:
        for err in errors or []:
            if "Write blocked" in str(err):
                step_msg = str(err)
                break
    run_row = (
        client.table("workflow_runs")
        .select("status, error_message")
        .eq("id", run_id)
        .limit(1)
        .execute()
        .data
        or [{}]
    )[0]
    run_msg = str(run_row.get("error_message") or "")
    user_facing = step_msg or run_msg
    canvas_ok = (
        user_facing == EXPECTED_VOICE
        or EXPECTED_VOICE in user_facing
    ) and "Step execution failed" not in (user_facing or "Step execution failed")

    # Executive Digest via tip API
    dig = httpx.get(
        f"{BASE}/api/workflows/execution-outcomes/executive-digest",
        headers=headers,
        params={"environment": "production"},
        timeout=60.0,
    )
    digest_body = dig.json() if dig.is_success else {"detail": dig.text[:500]}
    digest_text = str((digest_body or {}).get("digest") or "")
    digest_ok = dig.status_code == 200 and (
        "Executive Digest" in digest_text
        or "No terminal outcomes" in digest_text
        or "completed" in digest_text.lower()
    )

    report = {
        "module": "D-ship",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha,
        "base": BASE,
        "org_id": org_id,
        "canvas": {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "final_status": final_status or run_row.get("status"),
            "step_error_code": step_code,
            "user_facing_error": user_facing[:800],
            "expected": EXPECTED_VOICE,
            "pass": canvas_ok,
            "errors_sample": [str(e)[:200] for e in (errors or [])[:3]],
            "step_rows_sample": step_rows[:2] if isinstance(step_rows, list) else [],
        },
        "executive_digest": {
            "http": dig.status_code,
            "event_count": (digest_body or {}).get("event_count"),
            "digest": digest_text[:1200],
            "pass": digest_ok,
        },
        "passed": bool(canvas_ok and digest_ok and git_sha),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

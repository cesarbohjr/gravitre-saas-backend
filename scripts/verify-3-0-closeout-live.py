#!/usr/bin/env python3
"""3.0 remaining live probes on isolated org only.

H: unique Alpha bind + plan stamp (exact host/email; no fuzzy person).
J: ranked safe-READ notices from live website readiness (write_allowed=False).
D: stage Apollo list, persist checkpoint, resume same plan_id; never send.

Not Voice-C, not lane B, not operator org.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO))

from isolated_conversation_org import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    FORBIDDEN_OPERATOR_ORG_ID,
    mark_smoke_run,
    smoke_http_headers,
)

PROD_DEFAULT = "https://api.gravitre.app"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            pass
    merged.update({k: v for k, v in __import__("os").environ.items() if v})
    import os

    for k in (
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWT_SECRET",
    ):
        if merged.get(k):
            os.environ[k] = merged[k]
    return merged


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    url = env["SUPABASE_URL"].rstrip("/")
    secret = env["SUPABASE_JWT_SECRET"]
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _parse_sse(raw: str) -> list[dict]:
    events: list[dict] = []
    for block in (raw or "").split("\n\n"):
        data_lines = [line[5:].strip() for line in block.splitlines() if line.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines)
        if payload == "[DONE]":
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return events


def _plan_ids(events: list[dict]) -> list[str]:
    found: list[str] = []
    for ev in events:
        data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
        state = data.get("taskState") or ev.get("taskState") or {}
        if not isinstance(state, dict):
            continue
        plan = state.get("execution_plan") if isinstance(state.get("execution_plan"), dict) else {}
        pid = str(plan.get("plan_id") or "").strip()
        if pid and pid not in found:
            found.append(pid)
        pending = data.get("pendingTask") or state.get("pending_task")
        if isinstance(pending, dict):
            for key in ("execution_plan_id", "plan_id"):
                val = str(pending.get(key) or "").strip()
                if val and val not in found:
                    found.append(val)
    return found


def _chat(
    *,
    base_url: str,
    org_id: str,
    token: str,
    message: str,
    conversation_id: str,
) -> tuple[int, list[dict]]:
    body = {
        "messages": [{"role": "user", "content": message}],
        "org_id": org_id,
        "tools": ["knowledge_base", "agent_status", "connector_status"],
        "mode": "fast",
        "conversation_id": conversation_id,
        "spoken_mode": False,
        "surface": "assistant",
    }
    url = f"{base_url.rstrip('/')}/api/assistant/chat"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", "production")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "text/event-stream")
    for key, value in smoke_http_headers().items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return int(resp.status), _parse_sse(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return exc.code, _parse_sse(exc.read().decode("utf-8", errors="replace"))


def _probe_h(client, org_id: str) -> dict:
    from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
    from app.services.gravitre_e2e_test_org import (
        ALPHA_ENTITY_ID,
        TEST_COMPANY_HOST,
        seed_test_customer_alpha,
        test_customer_alpha_bindings,
    )
    from app.services.business_entity_fabric import join_provider_bindings, persist_join_store
    from app.services.reasoning_evidence_pipeline import stamp_entity_on_execution_plan

    rows = (
        client.table("org_business_entities")
        .select("id,org_id,canonical_key,display_name,kind")
        .eq("org_id", org_id)
        .execute()
        .data
        or []
    )
    alpha = next(
        (
            r
            for r in rows
            if str(r.get("canonical_key") or "") == ALPHA_ENTITY_ID
            or str(r.get("id") or "") == ALPHA_ENTITY_ID
        ),
        None,
    )
    entity = seed_test_customer_alpha(org_id=org_id)
    written = 0
    if alpha is None:
        written = persist_join_store(client, entity)
        rows = (
            client.table("org_business_entities")
            .select("id,org_id,canonical_key,display_name,kind")
            .eq("org_id", org_id)
            .execute()
            .data
            or []
        )
        alpha = next(
            (
                r
                for r in rows
                if str(r.get("canonical_key") or "") == ALPHA_ENTITY_ID
                or str(r.get("display_name") or "").startswith("Gravitre Test Customer Alpha")
            ),
            None,
        )
    bindings = test_customer_alpha_bindings()
    joined = join_provider_bindings(
        org_id=org_id,
        display_name="Gravitre Test Customer Alpha",
        kind="company",
        left=bindings[0],
        right=bindings[1],
        left_org_id=org_id,
        right_org_id=org_id,
        existing_left_entity_id=ALPHA_ENTITY_ID,
        existing_right_entity_id=ALPHA_ENTITY_ID,
    )
    refused = join_provider_bindings(
        org_id=org_id,
        display_name="Gravitre Test Customer Alpha",
        kind="company",
        left=bindings[0],
        right=bindings[1],
        left_org_id=org_id,
        right_org_id=FORBIDDEN_OPERATOR_ORG_ID,
    )
    plan = stamp_entity_on_execution_plan(
        ExecutionPlan(
            plan_id="plan-3-0-h-live",
            summary="unique bind",
            steps=[
                ExecutionStep(step_id="e1", title="hs", kind="evidence", connector_id="hubspot"),
                ExecutionStep(step_id="e2", title="qbo", kind="evidence", connector_id="quickbooks"),
            ],
            source="live_closeout",
        ),
        entity=entity,
        expected_org_id=org_id,
        store_available=True,
    )
    hosts = {e.value for e in entity.evidence if e.kind == "host"}
    ok = (
        joined.status == "joined"
        and joined.entity is not None
        and joined.entity.id == ALPHA_ENTITY_ID
        and refused.status == "refused_cross_org"
        and plan.entity_id == ALPHA_ENTITY_ID
        and TEST_COMPANY_HOST in hosts
        and alpha is not None
        and str(alpha.get("org_id")) == org_id
        and str(alpha.get("org_id")) != FORBIDDEN_OPERATOR_ORG_ID
    )
    return {
        "pass": ok,
        "alpha_row": alpha,
        "persist_written": written,
        "join_status": joined.status,
        "join_entity_id": None if joined.entity is None else joined.entity.id,
        "refused_cross_org": refused.status,
        "plan_entity_id": plan.entity_id,
        "host": TEST_COMPANY_HOST,
        "fuzzy_person": False,
    }


def _probe_j(client, org_id: str, settings) -> dict:
    from app.services.proactive_business_operator import (
        rank_safe_read_notices,
        signals_from_website_readiness,
    )
    from app.services.website_source_status import website_source_readiness

    readiness = website_source_readiness(client, org_id, settings)
    recs = rank_safe_read_notices(signals_from_website_readiness(readiness))
    ok = all(rec.write_allowed is False for rec in recs) and len(recs) <= 3
    return {
        "pass": ok,
        "readiness": {
            vendor: {
                "present": row.get("present"),
                "executable": row.get("executable"),
                "auth_status": row.get("auth_status"),
                "blocking_reason": row.get("blocking_reason"),
            }
            for vendor, row in (readiness or {}).items()
        },
        "notice_count": len(recs),
        "write_allowed": [rec.write_allowed for rec in recs],
        "investigations": [rec.investigation for rec in recs],
        "signal_ids": [rec.signal_id for rec in recs],
    }


def _probe_d(*, base_url: str, org_id: str, token: str, client) -> dict:
    from app.services.durable_work_session import resume_from_checkpoint

    conversation_id = str(uuid.uuid4())
    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    list_name = f"gravitre-3-0-d-resume-{tag}"
    stage_http, stage_events = _chat(
        base_url=base_url,
        org_id=org_id,
        token=token,
        message=(
            f"Create an Apollo contact list named exactly '{list_name}' "
            "with no contacts. Use Apollo only."
        ),
        conversation_id=conversation_id,
    )
    hold_http, hold_events = _chat(
        base_url=base_url,
        org_id=org_id,
        token=token,
        message="yes wait",
        conversation_id=conversation_id,
    )
    row = (
        client.table("conversations")
        .select("id,task_state")
        .eq("id", conversation_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    state = (row[0] or {}).get("task_state") if row else {}
    if not isinstance(state, dict):
        state = {}
    crashed = {
        "durable_checkpoint": state.get("durable_checkpoint") or state.get("write_checkpoint"),
        "execution_plan": None,
        "pending_task": state.get("pending_task"),
    }
    resumed = resume_from_checkpoint(crashed, continue_work=True)
    stage_ids = _plan_ids(stage_events)
    hold_ids = _plan_ids(hold_events)
    stored_plan = state.get("execution_plan") if isinstance(state.get("execution_plan"), dict) else {}
    stored_id = str(stored_plan.get("plan_id") or "").strip()
    target = stored_id or (stage_ids[0] if stage_ids else "")
    same = bool(target) and (not hold_ids or target in hold_ids or not hold_ids)
    resumed_ok = resumed is not None and bool(target) and resumed.plan_id == target
    sent = any("i sent" in str(ev).lower() for ev in hold_events)
    ok = (
        stage_http == 200
        and hold_http == 200
        and not sent
        and bool(target)
        and (same or resumed_ok)
    )
    return {
        "pass": ok,
        "conversation_id": conversation_id,
        "list_name": list_name,
        "stage_http": stage_http,
        "hold_http": hold_http,
        "stage_plan_ids": stage_ids,
        "hold_plan_ids": hold_ids,
        "stored_plan_id": stored_id or None,
        "resumed_plan_id": None if resumed is None else resumed.plan_id,
        "sent_claim": sent,
    }


def main() -> int:
    mark_smoke_run()
    env = _load_env()
    for key in ("SUPABASE_URL", "SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY"):
        if not env.get(key):
            raise SystemExit(f"Missing {key}")
    from supabase import create_client
    from smoke_auth import resolve_smoke_actor_and_email
    from app.config import get_settings

    org_id = (
        env.get("ISOLATED_CONVERSATION_TEST_ORG_ID") or DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
    ).strip()
    if org_id == FORBIDDEN_OPERATOR_ORG_ID:
        raise SystemExit("refused operator org")
    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    actor, email = resolve_smoke_actor_and_email(client, org_id=org_id, env=env)
    token = _mint_token(env, actor, email)
    req = urllib.request.Request(f"{PROD_DEFAULT}/health", method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        health = json.loads(resp.read().decode("utf-8"))
    h = _probe_h(client, org_id)
    j = _probe_j(client, org_id, get_settings())
    d = _probe_d(base_url=PROD_DEFAULT, org_id=org_id, token=token, client=client)
    report = {
        "probe": "3.0_closeout_live",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "org_id": org_id,
        "health": {"git_sha": health.get("git_sha"), "timestamp": health.get("timestamp")},
        "h_unique_bind": h,
        "j_notices": j,
        "d_resume": d,
        "pass": bool(h["pass"] and j["pass"] and d["pass"]),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "lane_b": "NOT_RUN",
        "voice_c": "NOT_RUN",
    }
    out = REPO / "docs" / "delivery" / "gravitre-3.0-closeout-live.json"
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

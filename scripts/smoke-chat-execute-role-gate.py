#!/usr/bin/env python3
"""Live 4d: non-approver POST /conversation/{id}/execute must be 403 server-side.

Mints a JWT for a known member (non-admin) when CHAT_GATE_MEMBER_USER_ID is set,
stages a fake awaiting_confirm pending_task on a conversation they own, then
calls execute and asserts HTTP 403.

Usage:
  python scripts/smoke-chat-execute-role-gate.py
"""
from __future__ import annotations

import json
import os
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

API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ORG = os.environ.get("SMOKE_ORG_ID", "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea")
ENV_NAME = "production"
OUT = REPO / "docs" / "delivery" / "chat-execute-role-gate-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            pass
    merged.update({k: v for k, v in os.environ.items() if v})
    for k, v in merged.items():
        os.environ.setdefault(k, v)
    return merged


def mint(env: dict[str, str], user_id: str, email: str) -> str:
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


def request(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict | str]:
    url = f"{API_BASE}{path}"
    url += ("&" if "?" in path else "?") + f"environment={ENV_NAME}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", ORG)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, raw


def main() -> int:
    env = load_env()
    member_id = os.environ.get("CHAT_GATE_MEMBER_USER_ID", "").strip()
    member_email = os.environ.get("CHAT_GATE_MEMBER_EMAIL", "member@example.com").strip()
    admin_id = os.environ.get("CHAT_GATE_ADMIN_USER_ID", "").strip()
    admin_email = os.environ.get("CHAT_GATE_ADMIN_EMAIL", "admin@example.com").strip()
    report: dict = {
        "ran_at": utcnow(),
        "api_base": API_BASE,
        "org_id": ORG,
        "verdict": "NOT RUN",
        "checks": [],
    }

    if not member_id:
        report["verdict"] = "BLOCKED"
        report["detail"] = "Set CHAT_GATE_MEMBER_USER_ID to a non-admin org member user id"
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    from app.workflows.repository import get_supabase_client
    from app.config import get_settings

    settings = get_settings()
    client = get_supabase_client(settings)
    role_row = (
        client.table("organization_members")
        .select("role")
        .eq("org_id", ORG)
        .eq("user_id", member_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    role = str((role_row[0] if role_row else {}).get("role") or "").lower()
    report["member_role"] = role
    if role in {"admin", "owner"}:
        report["verdict"] = "BLOCKED"
        report["detail"] = f"CHAT_GATE_MEMBER_USER_ID is {role}; need a member/viewer"
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    conv_id = str(uuid.uuid4())
    now = utcnow()
    client.table("conversations").upsert(
        {
            "id": conv_id,
            "org_id": ORG,
            "user_id": member_id,
            "title": "Role-gate smoke",
            "preview": "role-gate",
            "message_count": 0,
            "task_state": {
                "pending_task": {
                    "type": "connector_action",
                    "status": "awaiting_confirm",
                    "params": {
                        "tool_name": "slack_send_message",
                        "invoke_action": "slack.post_message",
                        "integration": "slack",
                        "kind": "write",
                        "label": "Post to Slack #general",
                        "args": {"channel": "general", "message": "role-gate probe"},
                        "channel": "general",
                        "message": "role-gate probe",
                        "status": "awaiting_confirm",
                    },
                }
            },
            "created_at": now,
            "updated_at": now,
        }
    ).execute()
    report["conversation_id"] = conv_id

    member_token = mint(env, member_id, member_email)
    status, body = request(
        "POST",
        f"/api/assistant/conversation/{conv_id}/execute",
        member_token,
        {"confirm": True},
    )
    report["checks"].append(
        {
            "name": "member_execute_forbidden",
            "status": status,
            "body": body,
            "pass": status == 403,
        }
    )

    if admin_id:
        admin_token = mint(env, admin_id, admin_email)
        # Admin may own a different conversation — role gate only applies to pending writes;
        # for this smoke we only assert member 403. Optional: confirm admin is not 403 on their own.
        a_status, a_body = request(
            "GET",
            "/api/approvals",
            admin_token,
        )
        report["checks"].append(
            {
                "name": "admin_list_approvals",
                "status": a_status,
                "pass": a_status == 200,
                "body_preview": str(a_body)[:300],
            }
        )

    # Cleanup staged conversation
    try:
        client.table("conversations").delete().eq("id", conv_id).eq("org_id", ORG).execute()
    except Exception as exc:  # noqa: BLE001
        report["cleanup_error"] = str(exc)

    member_ok = any(c["name"] == "member_execute_forbidden" and c["pass"] for c in report["checks"])
    report["verdict"] = "PASS" if member_ok else "FAIL"
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if member_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

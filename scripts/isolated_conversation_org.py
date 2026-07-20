#!/usr/bin/env python3
"""Dedicated isolated org for smoke/test/CI conversation writes.

NEVER point conversation-creating smokes at Cesar's workspace
(cbbf993b-b22f-41ce-964b-1fc25e0dd9ea) or any other customer-visible org.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO))

from app.services.conversation_write_guard import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    FORBIDDEN_OPERATOR_ORG_ID,
    ISOLATED_CONVERSATION_TEST_ORG_NAME,
    ISOLATED_CONVERSATION_TEST_ORG_SLUG,
    ConversationWriteBlockedError,
    assert_conversation_create_allowed,
    isolated_conversation_test_org_id,
    mark_smoke_run,
    smoke_http_headers,
)

SA_EMAIL = "conversation-smoke-sa@gravitre.app"
SA_FULL_NAME = "Gravitree Conversation Smoke SA"
# Provisioned 2026-07-19 against prod Supabase (smyeexlrqdpymwjmgzqu).
DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID = "a9f1240f-910a-42ca-aebf-38caeac288c3"

__all__ = [
    "DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID",
    "FORBIDDEN_OPERATOR_ORG_ID",
    "ISOLATED_CONVERSATION_TEST_ORG_NAME",
    "ISOLATED_CONVERSATION_TEST_ORG_SLUG",
    "ConversationWriteBlockedError",
    "SA_EMAIL",
    "assert_conversation_create_allowed",
    "ensure_isolated_conversation_test_org",
    "isolated_conversation_test_org_id",
    "mark_smoke_run",
    "resolve_isolated_conversation_actor",
    "smoke_http_headers",
]


def ensure_isolated_conversation_test_org(client: Any) -> tuple[str, str]:
    """Idempotently create the isolated org + service-account actor. Returns (org_id, user_id)."""
    org_id = isolated_conversation_test_org_id()
    existing = client.table("organizations").select("id,settings").eq("id", org_id).limit(1).execute()
    settings = {
        "isolated_conversation_test_org": True,
        "never_customer_visible": True,
        "purpose": "smoke_test_ci_conversation_writes_only",
    }
    if not existing.data:
        client.table("organizations").insert(
            {
                "id": org_id,
                "name": ISOLATED_CONVERSATION_TEST_ORG_NAME,
                "slug": ISOLATED_CONVERSATION_TEST_ORG_SLUG,
                "status": "active",
                "settings": settings,
            }
        ).execute()
    else:
        row_settings = dict((existing.data[0] or {}).get("settings") or {})
        if not row_settings.get("isolated_conversation_test_org"):
            row_settings.update(settings)
            client.table("organizations").update({"settings": row_settings}).eq("id", org_id).execute()

    user_id = (
        (os.environ.get("ISOLATED_CONVERSATION_TEST_USER_ID") or "").strip()
        or DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID
    )
    if user_id:
        try:
            client.auth.admin.get_user_by_id(user_id)
        except Exception:
            user_id = ""

    if not user_id:
        # Prefer existing SA by email (list may paginate — also try create+catch).
        try:
            listed = client.auth.admin.list_users()
            users = getattr(listed, "users", None) or []
            for u in users:
                if (getattr(u, "email", None) or "").lower() == SA_EMAIL:
                    user_id = str(u.id)
                    break
        except Exception:
            user_id = ""

    if not user_id:
        try:
            created = client.auth.admin.create_user(
                {
                    "email": SA_EMAIL,
                    "email_confirm": True,
                    "user_metadata": {
                        "full_name": SA_FULL_NAME,
                        "company_name": ISOLATED_CONVERSATION_TEST_ORG_NAME,
                        "isolated_conversation_smoke_sa": True,
                    },
                }
            )
            user_id = str(created.user.id)
        except Exception as exc:
            # Email already registered — fall back to known provisioned id.
            if DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID:
                user_id = DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID
            else:
                raise SystemExit(f"Unable to provision conversation smoke SA: {exc}") from exc

    member = (
        client.table("organization_members")
        .select("id")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not member.data:
        client.table("organization_members").insert(
            {"org_id": org_id, "user_id": user_id, "role": "admin"}
        ).execute()

    os.environ.setdefault("ISOLATED_CONVERSATION_TEST_ORG_ID", org_id)
    os.environ.setdefault("ISOLATED_CONVERSATION_TEST_USER_ID", user_id)
    return org_id, user_id


def resolve_isolated_conversation_actor(
    env: dict[str, str],
    client: Any | None = None,
    *,
    provision: bool = True,
) -> tuple[str, str, str]:
    """Return (org_id, user_id, email) for conversation smokes; marks smoke run.

    Raises ConversationWriteBlockedError if env still points at the operator org.
    """
    mark_smoke_run()
    org_id = (
        (env.get("ISOLATED_CONVERSATION_TEST_ORG_ID") or "").strip()
        or isolated_conversation_test_org_id()
    )
    if org_id.lower() == FORBIDDEN_OPERATOR_ORG_ID.lower():
        raise ConversationWriteBlockedError(
            f"ISOLATED_CONVERSATION_TEST_ORG_ID must not be operator org {FORBIDDEN_OPERATOR_ORG_ID}"
        )
    assert_conversation_create_allowed(org_id)

    user_id = (
        (env.get("ISOLATED_CONVERSATION_TEST_USER_ID") or "").strip()
        or DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID
    )
    email = SA_EMAIL

    if client is not None and provision:
        org_id, user_id = ensure_isolated_conversation_test_org(client)
        try:
            users = client.auth.admin.get_user_by_id(user_id)
            email = (users.user.email if users and users.user else None) or SA_EMAIL
        except Exception:
            email = SA_EMAIL
    elif not user_id:
        raise SystemExit(
            "Set ISOLATED_CONVERSATION_TEST_USER_ID or call with client= to provision the SA actor"
        )

    env["ISOLATED_CONVERSATION_TEST_ORG_ID"] = org_id
    env["ISOLATED_CONVERSATION_TEST_USER_ID"] = user_id
    os.environ["ISOLATED_CONVERSATION_TEST_ORG_ID"] = org_id
    os.environ["ISOLATED_CONVERSATION_TEST_USER_ID"] = user_id
    return org_id, user_id, email


def _load_env_files() -> dict[str, str]:
    from dotenv import dotenv_values

    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        loaded = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if loaded:
            merged.update({k: v for k, v in loaded.items() if v})
    return merged


def main() -> int:
    from supabase import create_client

    merged = _load_env_files()
    merged.update({k: v for k, v in os.environ.items() if v})
    url = merged.get("SUPABASE_URL")
    key = merged.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    client = create_client(url, key)
    org_id, user_id, email = resolve_isolated_conversation_actor(merged, client)
    print(f"isolated_org_id={org_id}")
    print(f"isolated_user_id={user_id}")
    print(f"isolated_email={email}")
    print(f"slug={ISOLATED_CONVERSATION_TEST_ORG_SLUG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

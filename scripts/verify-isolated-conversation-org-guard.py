#!/usr/bin/env python3
"""Live verification: isolated-org write PASS + non-test org FAIL loudly.

Evidence bar for conversation_write_guard:
1) smoke context + isolated org → ensure_owned_conversation inserts a row
2) smoke context + operator org → ConversationWriteBlockedError (no insert)
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO / "scripts"))

from dotenv import dotenv_values  # noqa: E402

from isolated_conversation_org import (  # noqa: E402
    FORBIDDEN_OPERATOR_ORG_ID,
    assert_conversation_create_allowed,
    mark_smoke_run,
    resolve_isolated_conversation_actor,
)
from app.services.conversation_state_service import ConversationStateService  # noqa: E402
from app.services.conversation_write_guard import ConversationWriteBlockedError  # noqa: E402


def _load_env() -> dict[str, str]:
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
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


async def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    org_id, user_id, email = resolve_isolated_conversation_actor(env, client)
    mark_smoke_run()

    print(f"isolated_org={org_id}")
    print(f"actor={user_id} email={email}")

    # --- 1) Allowed write into isolated org ---
    conv_id = str(uuid.uuid4())
    service = ConversationStateService(settings)
    ensured = await service.ensure_owned_conversation(
        org_id=org_id,
        user_id=user_id,
        conversation_id=conv_id,
        title=f"Isolated guard verify {datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        client=client,
    )
    assert ensured == conv_id, ensured
    row = (
        client.table("conversations")
        .select("id, org_id, user_id, title")
        .eq("id", conv_id)
        .limit(1)
        .execute()
    )
    assert row.data, "expected conversation row in isolated org"
    assert str(row.data[0]["org_id"]) == org_id
    print(f"PASS write_isolated conversation_id={conv_id}")

    # --- 2) Loud fail when pointing at operator / non-test org ---
    blocked = False
    try:
        assert_conversation_create_allowed(FORBIDDEN_OPERATOR_ORG_ID)
    except ConversationWriteBlockedError as exc:
        blocked = True
        print(f"PASS refuse_operator_org: {exc}")
    if not blocked:
        raise SystemExit("FAIL: expected ConversationWriteBlockedError for operator org")

    blocked2 = False
    bad_conv = str(uuid.uuid4())
    try:
        await service.ensure_owned_conversation(
            org_id=FORBIDDEN_OPERATOR_ORG_ID,
            user_id=user_id,
            conversation_id=bad_conv,
            title="should-not-insert",
            client=client,
        )
    except ConversationWriteBlockedError as exc:
        blocked2 = True
        print(f"PASS ensure_owned_refuses_operator: {exc}")
    if not blocked2:
        raise SystemExit("FAIL: ensure_owned_conversation did not raise for operator org")

    leaked = (
        client.table("conversations")
        .select("id")
        .eq("id", bad_conv)
        .limit(1)
        .execute()
    )
    if leaked.data:
        raise SystemExit(f"FAIL: leaked conversation row into operator org id={bad_conv}")
    print("PASS no_operator_row_leaked")

    # Cleanup verify row (best-effort)
    try:
        client.table("conversations").delete().eq("id", conv_id).eq("org_id", org_id).execute()
    except Exception as exc:  # noqa: BLE001
        print(f"cleanup_warn={exc}")

    print("ALL_PASS isolated_conversation_org_guard")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

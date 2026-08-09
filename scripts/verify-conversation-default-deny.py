#!/usr/bin/env python3
"""Live proof: default-deny for test credentials (flagged AND unflagged)."""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "scripts"))

from dotenv import dotenv_values  # noqa: E402

from app.services.conversation_state_service import ConversationStateService  # noqa: E402
from app.services.conversation_write_guard import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
    FORBIDDEN_OPERATOR_ORG_ID,
    ConversationWriteBlockedError,
    assert_conversation_create_allowed,
    clear_request_actor,
    mark_smoke_run,
    set_smoke_run_context,
)


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(path, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
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
    service = ConversationStateService(settings)
    sa = DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID

    # --- A) Unflagged smoke SA → Cesar org must refuse (default-deny) ---
    set_smoke_run_context(False)
    clear_request_actor()
    os.environ.pop("GRAVITRE_SMOKE_RUN", None)
    try:
        assert_conversation_create_allowed(
            FORBIDDEN_OPERATOR_ORG_ID,
            actor_id=sa,
            actor_email="conversation-smoke-sa@gravitre.app",
        )
        print("FAIL_UNFLAGGED_ASSERT: no raise")
        return 2
    except ConversationWriteBlockedError as exc:
        print(f"PASS_UNFLAGGED_ASSERT: {exc}")

    bad1 = str(uuid.uuid4())
    try:
        await service.ensure_owned_conversation(
            org_id=FORBIDDEN_OPERATOR_ORG_ID,
            user_id=sa,
            conversation_id=bad1,
            title="default-deny-unflagged-must-fail",
            client=client,
        )
        print("FAIL_UNFLAGGED_ENSURE: no raise")
        return 2
    except ConversationWriteBlockedError as exc:
        print(f"PASS_UNFLAGGED_ENSURE: {exc}")
    leaked1 = client.table("conversations").select("id").eq("id", bad1).limit(1).execute()
    print(f"leaked_unflagged={bool(leaked1.data)}")
    if leaked1.data:
        return 2

    # --- B) Flagged (legacy opt-in belt) → Cesar org must refuse ---
    mark_smoke_run()
    bad2 = str(uuid.uuid4())
    try:
        await service.ensure_owned_conversation(
            org_id=FORBIDDEN_OPERATOR_ORG_ID,
            user_id=sa,
            conversation_id=bad2,
            title="default-deny-flagged-must-fail",
            client=client,
        )
        print("FAIL_FLAGGED_ENSURE: no raise")
        return 2
    except ConversationWriteBlockedError as exc:
        print(f"PASS_FLAGGED_ENSURE: {exc}")
    leaked2 = client.table("conversations").select("id").eq("id", bad2).limit(1).execute()
    print(f"leaked_flagged={bool(leaked2.data)}")
    if leaked2.data:
        return 2

    print("ALL_PASS conversation_default_deny")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

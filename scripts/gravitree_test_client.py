#!/usr/bin/env python3
"""Mandatory harness for smoke/CI scripts that write conversations (or resolve orgs).

Import this module instead of constructing ad-hoc Supabase clients + org IDs.
Hard rules:
  * Conversation writes target the isolated org only — OAUTH_SMOKE_ORG_ID is ignored.
  * Operator workspace overrides are refused loudly.
  * mark_smoke_run() is engaged on import for in-process guard belts.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
    FORBIDDEN_OPERATOR_ORG_ID,
    SA_EMAIL,
    ConversationWriteBlockedError,
    assert_conversation_create_allowed,
    isolated_conversation_test_org_id,
    mark_smoke_run,
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

# Engage smoke belt as soon as a script imports the harness.
mark_smoke_run()

__all__ = [
    "FORBIDDEN_OPERATOR_ORG_ID",
    "ISOLATED_ORG_ID",
    "ISOLATED_USER_ID",
    "ConversationWriteBlockedError",
    "assert_conversation_create_allowed",
    "get_service_client",
    "isolated_org_id",
    "load_env",
    "refuse_org_override",
    "require_isolated_org",
    "resolve_test_actor",
    "smoke_http_headers",
]

ISOLATED_ORG_ID = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
ISOLATED_USER_ID = DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID


def load_env() -> dict[str, str]:
    from dotenv import dotenv_values

    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
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


def get_service_client(env: dict[str, str] | None = None) -> Any:
    """Service-role Supabase client — only path scripts should use for writes."""
    from supabase import create_client

    merged = dict(env or load_env())
    url = merged.get("SUPABASE_URL")
    key = merged.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    mark_smoke_run()
    return create_client(url, key)


def isolated_org_id() -> str:
    return isolated_conversation_test_org_id()


def refuse_org_override(org_id: str | None, *, actor_id: str | None = None) -> None:
    """Refuse any attempt to point conversation writes at a non-isolated org."""
    assert_conversation_create_allowed(
        org_id,
        actor_id=actor_id or ISOLATED_USER_ID,
        actor_email=SA_EMAIL,
    )


def require_isolated_org(requested: str | None = None) -> str:
    """Return the isolated org id. Non-isolated overrides raise.

    Ignores OAUTH_SMOKE_ORG_ID / SMOKE_ORG_ID — those historically pointed at Cesar's org.
    """
    mark_smoke_run()
    allowed = isolated_org_id()
    req = (requested or "").strip()
    if not req:
        return allowed
    if req.lower() == FORBIDDEN_OPERATOR_ORG_ID.lower():
        raise ConversationWriteBlockedError(
            f"REFUSING org override to operator workspace {FORBIDDEN_OPERATOR_ORG_ID}. "
            f"Use isolated org {allowed} only."
        )
    if req.lower() != allowed.lower():
        raise ConversationWriteBlockedError(
            f"REFUSING org override {req!r}. Conversation smoke harness allows only {allowed}."
        )
    return allowed


def resolve_test_actor(
    env: dict[str, str] | None = None,
    client: Any | None = None,
) -> tuple[str, str, str]:
    """(org_id, user_id, email) for the isolated conversation smoke SA."""
    merged = dict(env or load_env())
    # Strip operator-org inheritance — harness owns org selection.
    merged.pop("OAUTH_SMOKE_ORG_ID", None)
    merged.pop("SMOKE_ORG_ID", None)
    os.environ.pop("OAUTH_SMOKE_ORG_ID", None)
    db = client or get_service_client(merged)
    return resolve_isolated_conversation_actor(merged, db)

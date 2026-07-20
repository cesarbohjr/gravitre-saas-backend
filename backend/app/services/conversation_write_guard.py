"""Hard guard: smoke/test/CI must not create conversations in real orgs.

Standing rule — conversation rows from automated runs land only in the dedicated
isolated test org. Misconfigured scripts must fail loudly (raise), never skip.
"""
from __future__ import annotations

import os
from contextvars import ContextVar

# Well-known isolated conversation-smoke org (never a customer / operator UI org).
# Distinct from Cesar workspace cbbf993b-b22f-41ce-964b-1fc25e0dd9ea.
DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID = "f07e57c0-1501-4000-8000-c04e57a00001"
ISOLATED_CONVERSATION_TEST_ORG_SLUG = "gravitre-isolated-conversation-smoke"
ISOLATED_CONVERSATION_TEST_ORG_NAME = "Gravitre Isolated Conversation Smoke"

# Operator workspace that was historically polluted by smokes — never treat as isolated.
FORBIDDEN_OPERATOR_ORG_ID = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"

SMOKE_RUN_HEADER = "x-gravitree-smoke-run"

_smoke_run_ctx: ContextVar[bool] = ContextVar("gravitree_smoke_run", default=False)


class ConversationWriteBlockedError(RuntimeError):
    """Raised when a smoke/test/CI context targets a non-isolated org."""


def set_smoke_run_context(enabled: bool) -> None:
    """Set request/process smoke flag (middleware + in-process scripts)."""
    _smoke_run_ctx.set(bool(enabled))


def mark_smoke_run() -> None:
    """Flag the current process as a smoke/test/CI conversation writer."""
    os.environ["GRAVITREE_SMOKE_RUN"] = "1"
    set_smoke_run_context(True)


def isolated_conversation_test_org_id() -> str:
    return (
        (os.environ.get("ISOLATED_CONVERSATION_TEST_ORG_ID") or "").strip()
        or DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
    )


def is_isolated_conversation_test_org(org_id: str | None) -> bool:
    oid = (org_id or "").strip().lower()
    if not oid:
        return False
    return oid == isolated_conversation_test_org_id().lower()


def _env_truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def is_smoke_test_ci_context() -> bool:
    """True when the calling context is flagged as smoke / test / CI automation.

    Detection is opt-in only (ContextVar / explicit env). Bare ``CI=true`` on an
    API host must never engage the guard — real traffic must keep working.
    Smoke scripts call ``mark_smoke_run()`` (or send ``X-Gravitree-Smoke-Run``).
    """
    if _smoke_run_ctx.get():
        return True
    if _env_truthy("GRAVITREE_SMOKE_RUN"):
        return True
    if _env_truthy("GRAVITREE_CONVERSATION_SMOKE"):
        return True
    return False


def assert_conversation_create_allowed(org_id: str | None) -> None:
    """Reject conversation creation for smoke/test/CI outside the isolated org.

    Fail loudly — callers must not catch-and-skip this error.
    """
    if not is_smoke_test_ci_context():
        return
    oid = (org_id or "").strip()
    allowed = isolated_conversation_test_org_id()
    if is_isolated_conversation_test_org(oid):
        return
    raise ConversationWriteBlockedError(
        "REFUSING conversation create: smoke/test/CI context cannot write "
        f"conversations into org {oid or '<missing>'!r}. "
        f"Target the isolated test org only ({allowed} / "
        f"{ISOLATED_CONVERSATION_TEST_ORG_SLUG}). "
        "Set ISOLATED_CONVERSATION_TEST_ORG_ID + GRAVITREE_SMOKE_RUN=1 "
        "(and X-Gravitree-Smoke-Run: 1 for HTTP). "
        f"Operator workspace {FORBIDDEN_OPERATOR_ORG_ID} is never allowed."
    )


def smoke_http_headers() -> dict[str, str]:
    """Headers every smoke HTTP client must send so the API guard engages."""
    return {SMOKE_RUN_HEADER: "1", "X-Gravitree-Smoke-Run": "1"}

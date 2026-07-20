"""Hard guard: test/service credentials cannot create conversations in real orgs.

Default-deny for known smoke/CI/service-account identities — callers do NOT need
to remember mark_smoke_run(). Opt-in smoke flags remain as a second belt for
scripts that still mint real-user JWTs under automation.
"""
from __future__ import annotations

import os
import re
from contextvars import ContextVar

# Well-known isolated conversation-smoke org (never a customer / operator UI org).
# Distinct from Cesar workspace cbbf993b-b22f-41ce-964b-1fc25e0dd9ea.
DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID = "f07e57c0-1501-4000-8000-c04e57a00001"
ISOLATED_CONVERSATION_TEST_ORG_SLUG = "gravitre-isolated-conversation-smoke"
ISOLATED_CONVERSATION_TEST_ORG_NAME = "Gravitre Isolated Conversation Smoke"

# Operator workspace that was historically polluted by smokes — never treat as isolated.
FORBIDDEN_OPERATOR_ORG_ID = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"

# Provisioned conversation smoke SA (prod Supabase smyeexlrqdpymwjmgzqu).
DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID = "a9f1240f-910a-42ca-aebf-38caeac288c3"
DEFAULT_ISOLATED_CONVERSATION_TEST_EMAIL = "conversation-smoke-sa@gravitre.app"

SMOKE_RUN_HEADER = "x-gravitree-smoke-run"

_smoke_run_ctx: ContextVar[bool] = ContextVar("gravitree_smoke_run", default=False)
_request_actor_id_ctx: ContextVar[str | None] = ContextVar("gravitree_request_actor_id", default=None)
_request_actor_email_ctx: ContextVar[str | None] = ContextVar(
    "gravitree_request_actor_email", default=None
)

_SMOKE_EMAIL_RE = re.compile(
    r"(^conversation-smoke-sa@)|(^ci\+)|(^smoke[-+.]|[-+. ]smoke@)|(@.*\.smoke\.gravitre\.app$)",
    re.IGNORECASE,
)


class ConversationWriteBlockedError(RuntimeError):
    """Raised when a smoke/test/CI context targets a non-isolated org."""


def set_smoke_run_context(enabled: bool) -> None:
    """Set request/process smoke flag (middleware + in-process scripts)."""
    _smoke_run_ctx.set(bool(enabled))


def mark_smoke_run() -> None:
    """Flag the current process as a smoke/test/CI conversation writer."""
    os.environ["GRAVITREE_SMOKE_RUN"] = "1"
    set_smoke_run_context(True)


def bind_request_actor(*, actor_id: str | None = None, actor_email: str | None = None) -> None:
    """Bind JWT/service actor for the current request/task (cleared by middleware)."""
    _request_actor_id_ctx.set((actor_id or "").strip() or None)
    _request_actor_email_ctx.set((actor_email or "").strip().lower() or None)


def clear_request_actor() -> None:
    _request_actor_id_ctx.set(None)
    _request_actor_email_ctx.set(None)


def isolated_conversation_test_org_id() -> str:
    return (
        (os.environ.get("ISOLATED_CONVERSATION_TEST_ORG_ID") or "").strip()
        or DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
    )


def isolated_conversation_test_user_id() -> str:
    return (
        (os.environ.get("ISOLATED_CONVERSATION_TEST_USER_ID") or "").strip()
        or DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID
    )


def is_isolated_conversation_test_org(org_id: str | None) -> bool:
    oid = (org_id or "").strip().lower()
    if not oid:
        return False
    return oid == isolated_conversation_test_org_id().lower()


def _env_truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def restricted_test_user_ids() -> set[str]:
    ids = {isolated_conversation_test_user_id().lower(), DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID.lower()}
    extra = (os.environ.get("CONVERSATION_TEST_USER_IDS") or "").strip()
    for part in extra.split(","):
        pid = part.strip().lower()
        if pid:
            ids.add(pid)
    return {i for i in ids if i}


def restricted_test_emails() -> set[str]:
    emails = {DEFAULT_ISOLATED_CONVERSATION_TEST_EMAIL.lower()}
    extra = (os.environ.get("CONVERSATION_TEST_EMAILS") or "").strip()
    for part in extra.split(","):
        email = part.strip().lower()
        if email:
            emails.add(email)
    return emails


def is_restricted_test_credential(
    *,
    actor_id: str | None = None,
    actor_email: str | None = None,
) -> bool:
    """True when the credential itself is a known smoke/CI/service-account identity.

    This is default-deny — independent of mark_smoke_run().
    """
    aid = (actor_id or _request_actor_id_ctx.get() or "").strip().lower()
    email = (actor_email or _request_actor_email_ctx.get() or "").strip().lower()
    if aid and aid in restricted_test_user_ids():
        return True
    if email and email in restricted_test_emails():
        return True
    if email and _SMOKE_EMAIL_RE.search(email):
        return True
    return False


def is_smoke_test_ci_context() -> bool:
    """True when the calling context is flagged as smoke / test / CI automation.

    Opt-in belt for automation that still uses a real-user JWT. Bare ``CI=true``
    on an API host must never engage this flag alone — real traffic must keep working.
    """
    if _smoke_run_ctx.get():
        return True
    if _env_truthy("GRAVITREE_SMOKE_RUN"):
        return True
    if _env_truthy("GRAVITREE_CONVERSATION_SMOKE"):
        return True
    return False


def is_conversation_write_restricted(
    *,
    actor_id: str | None = None,
    actor_email: str | None = None,
) -> bool:
    """Default-deny when credential is a test identity OR smoke context is flagged."""
    if is_restricted_test_credential(actor_id=actor_id, actor_email=actor_email):
        return True
    if is_smoke_test_ci_context():
        return True
    return False


def assert_org_write_allowed(
    org_id: str | None,
    *,
    actor_id: str | None = None,
    actor_email: str | None = None,
    resource: str = "org write",
) -> None:
    """Reject restricted-credential writes outside the allow-listed isolated org.

    Shared Module 0 choke for conversation create, tool invoke, Meson deploy, and
    platform assistant writes — same allow-list, same fail-loud contract.
    """
    if not is_conversation_write_restricted(actor_id=actor_id, actor_email=actor_email):
        return
    oid = (org_id or "").strip()
    allowed = isolated_conversation_test_org_id()
    if is_isolated_conversation_test_org(oid):
        return
    aid = (actor_id or _request_actor_id_ctx.get() or "").strip() or "<unknown>"
    raise ConversationWriteBlockedError(
        f"REFUSING {resource}: test/service credential cannot write "
        f"into org {oid or '<missing>'!r} (actor={aid}). "
        f"Allow-listed org only: {allowed} / {ISOLATED_CONVERSATION_TEST_ORG_SLUG}. "
        "Do not use OAUTH_SMOKE_ORG_ID / operator workspace for conversation writes. "
        f"Operator workspace {FORBIDDEN_OPERATOR_ORG_ID} is never allowed."
    )


def assert_conversation_create_allowed(
    org_id: str | None,
    *,
    actor_id: str | None = None,
    actor_email: str | None = None,
) -> None:
    """Reject conversation creation for restricted identities outside the allow-listed org.

    Fail loudly — callers must not catch-and-skip this error.
    """
    assert_org_write_allowed(
        org_id,
        actor_id=actor_id,
        actor_email=actor_email,
        resource="conversation create",
    )


def smoke_http_headers() -> dict[str, str]:
    """Headers smoke HTTP clients should send (second belt; credential check is primary)."""
    return {SMOKE_RUN_HEADER: "1", "X-Gravitree-Smoke-Run": "1"}

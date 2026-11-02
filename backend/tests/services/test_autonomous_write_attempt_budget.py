"""No autonomous write retries behind a single durable claim."""
from types import SimpleNamespace
from app.services.tool_service import _invoke_attempt_budget


def test_autonomous_write_is_single_attempt_even_when_global_retries_enabled():
    ctx = SimpleNamespace(autonomous_write_guarded=True)
    assert _invoke_attempt_budget(ctx, "hubspot.contacts.update") == 1
    assert _invoke_attempt_budget(ctx, "gmail.messages.send") == 1


def test_non_autonomous_calls_retain_existing_retry_policy():
    ctx = SimpleNamespace(autonomous_write_guarded=False)
    assert _invoke_attempt_budget(ctx, "hubspot.contacts.update") > 1

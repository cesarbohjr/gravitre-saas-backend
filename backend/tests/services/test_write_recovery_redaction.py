"""Recovery request persistence must never include connector credentials."""
from app.services.write_invoke_idempotency import _redact_recovery_args


def test_recovery_context_recursively_redacts_credentials():
    original = {
        "email": "a@example.invalid",
        "password": "top-secret",
        "headers": {"Authorization": "Bearer private", "Cookie": "sid=private"},
        "properties": [{"name": "Lead", "access_token": "private-token"}],
        "_gravitre_idempotency_key": "transport-only",
    }
    cleaned = _redact_recovery_args(original)
    assert cleaned["email"] == "a@example.invalid"
    assert cleaned["password"] == "[REDACTED]"
    assert cleaned["headers"]["Authorization"] == "[REDACTED]"
    assert cleaned["headers"]["Cookie"] == "[REDACTED]"
    assert cleaned["properties"][0]["name"] == "Lead"
    assert cleaned["properties"][0]["access_token"] == "[REDACTED]"
    assert "_gravitre_idempotency_key" not in cleaned
    assert original["password"] == "top-secret"

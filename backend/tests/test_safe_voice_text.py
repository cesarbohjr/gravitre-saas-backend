"""safe_voice_text is the content backstop behind the AST shape guard.

The scanner rejects text built inline at an emission site, but a local variable
holding raw text satisfies that shape. This closes the same gap by inspecting
what the string says instead of proving where it came from.
"""

from __future__ import annotations

import pytest

from app.services.composer_failure_triggers import VOICE_TURN_FAILURE_MESSAGE
from app.services.response_composer import TTS_SAFE_ERROR, safe_voice_text


@pytest.mark.parametrize(
    "raw",
    [
        "Traceback (most recent call last):\n  File \"x.py\", line 2",
        "sqlalchemy.exc.OperationalError: statement timeout",
        "psycopg2.errors.QueryCanceled",
        "SQLSTATE 57014",
        "RuntimeError: kernel exploded",
        "CognitiveTurnKernel failed to plan",
        'File "backend/app/services/x.py", line 41',
        "permission_denied",
        "statement_timeout",
        VOICE_TURN_FAILURE_MESSAGE,
    ],
)
def test_backend_shaped_text_never_reaches_the_listener(raw: str) -> None:
    assert safe_voice_text(raw) == TTS_SAFE_ERROR


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_it_fails_closed_rather_than_silent(blank: str | None) -> None:
    """Silence during a failure reads as the product hanging, so substitute."""
    assert safe_voice_text(blank) == TTS_SAFE_ERROR


@pytest.mark.parametrize(
    "ok",
    [
        "I couldn't reach HubSpot just now.",
        "That needs permission I don't have yet. Want me to request it?",
        "Done. Six contacts updated.",
        "Which of the two Acme accounts did you mean?",
    ],
)
def test_composed_language_passes_through_unchanged(ok: str) -> None:
    """The gate must not flatten real composed prose into the fallback."""
    assert safe_voice_text(ok) == ok


def test_the_local_variable_bypass_is_what_this_catches() -> None:
    """The exact shape the AST guard cannot see.

    `msg = str(exc)` then `ErrorFrame(error=msg)` passes the shape check, because
    the argument is a plain reference. The content check is what stops it.
    """
    exc = RuntimeError("sqlalchemy.exc.OperationalError: statement timeout")
    laundered_through_a_local = str(exc)
    assert safe_voice_text(laundered_through_a_local) == TTS_SAFE_ERROR

"""QA-force voice errors must stay gated and map to real error_class payloads."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.voice_provider_errors import error_public_payload
from app.services.voice_qa_hooks import (
    QA_FORCE_VOICE_ERROR_HEADER,
    forced_voice_provider_error,
    resolve_qa_force_voice_error,
)


def test_header_constant():
    assert QA_FORCE_VOICE_ERROR_HEADER == "X-Gravitre-QA-Force-Voice-Error"


def test_resolve_disabled_when_setting_off():
    settings = MagicMock(unified_turn_qa_hooks_enabled=False)
    assert resolve_qa_force_voice_error(settings, header_value="billing") is None


def test_resolve_billing_from_header():
    settings = MagicMock(unified_turn_qa_hooks_enabled=True)
    assert resolve_qa_force_voice_error(settings, header_value="billing") == "billing"


def test_resolve_rejects_unknown():
    settings = MagicMock(unified_turn_qa_hooks_enabled=True)
    with pytest.raises(ValueError, match="unknown QA force voice error"):
        resolve_qa_force_voice_error(settings, header_value="not-a-class")


def test_forced_billing_public_payload_matches_phase0_shape():
    exc = forced_voice_provider_error("billing")
    assert exc.status_code == 402
    assert exc.error_class == "billing"
    payload = error_public_payload(exc)
    assert payload["billing_issue"] is True
    assert payload["error_class"] == "billing"
    assert "billing" in payload["detail"].lower()

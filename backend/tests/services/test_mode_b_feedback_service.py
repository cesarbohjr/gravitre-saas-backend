"""Tests for Mode B feedback infrastructure (STA-293)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.feedback_mode_constants import FEEDBACK_MODE_A, FEEDBACK_MODE_B
from app.services.mode_b_feedback_service import (
    ModeBCapExceededError,
    ModeBFeedbackService,
    ModeBNotEnabledError,
)


@pytest.fixture
def service() -> ModeBFeedbackService:
    return ModeBFeedbackService(settings=MagicMock())


def _mock_settings_query(client: MagicMock, data: list | None = None) -> MagicMock:
    chain = (
        client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value
    )
    chain.data = data if data is not None else []
    return chain


def test_assert_cycle_cap_allows_shift_within_limit(service: ModeBFeedbackService):
    service.assert_cycle_cap_allows_shift(
        {"max_shift_percent_per_cycle": 15, "cycle_shift_total": 5},
        10,
    )


def test_assert_cycle_cap_blocks_when_exceeded(service: ModeBFeedbackService):
    with pytest.raises(ModeBCapExceededError):
        service.assert_cycle_cap_allows_shift(
            {
                "max_shift_percent_per_cycle": 15,
                "cycle_shift_total": 12,
                "cycle_started_at": datetime.now(timezone.utc).isoformat(),
            },
            5,
        )


@pytest.mark.asyncio
async def test_set_feedback_mode_b_requires_risk_ack(service: ModeBFeedbackService):
    with patch.object(service, "_client", return_value=MagicMock()):
        with pytest.raises(Exception) as exc:
            await service.set_feedback_mode(
                "org-1",
                feedback_mode=FEEDBACK_MODE_B,
                risk_acknowledged=False,
            )
        assert exc.value.code == "MODE_B_RISK_ACK_REQUIRED"


@pytest.mark.asyncio
async def test_apply_autonomous_mutation_requires_mode_b(service: ModeBFeedbackService):
    client = MagicMock()
    _mock_settings_query(client)
    with patch.object(service, "_client", return_value=client):
        with pytest.raises(ModeBNotEnabledError):
            await service.apply_autonomous_mutation("org-1", "agent-1", dimension="tone")


@pytest.mark.asyncio
async def test_run_replanning_cycle_requires_mode_b(service: ModeBFeedbackService):
    client = MagicMock()
    _mock_settings_query(client)
    with patch.object(service, "_client", return_value=client):
        with pytest.raises(ModeBNotEnabledError):
            await service.run_replanning_cycle("org-1")


@pytest.mark.asyncio
async def test_default_settings_use_mode_a(service: ModeBFeedbackService):
    client = MagicMock()
    _mock_settings_query(client)
    with patch.object(service, "_client", return_value=client):
        settings = await service.get_feedback_settings("org-1")
    assert settings["feedbackMode"] == FEEDBACK_MODE_A


@pytest.mark.asyncio
async def test_set_feedback_mode_a(service: ModeBFeedbackService):
    client = MagicMock()
    table = MagicMock()
    client.table.return_value = table
    _mock_settings_query(client)
    table.insert.return_value.execute.return_value.data = [
        {"org_id": "org-1", "pack_slug": "", "feedback_mode": FEEDBACK_MODE_A}
    ]
    with patch.object(service, "_client", return_value=client):
        with patch("app.services.mode_b_feedback_service.write_audit_event"):
            with patch.object(service, "record_autonomous_event", new=AsyncMock()):
                result = await service.set_feedback_mode(
                    "org-1",
                    feedback_mode=FEEDBACK_MODE_A,
                    actor_id="user-1",
                )
    assert result["feedbackMode"] == FEEDBACK_MODE_A

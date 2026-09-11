"""Unit coverage for OutcomeLearningService.fetch_recent_events (Phase 2, 2026-09-11).

Verifies the real hour-level cutoff filtering that backs the Intelligence Core
state endpoint -- added because /api/intelligence/core/state's own tests mock
this method out entirely, so the actual cutoff arithmetic needs its own check.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.outcome_learning_service import OutcomeLearningService


@pytest.mark.asyncio
async def test_fetch_recent_events_excludes_rows_older_than_window():
    service = OutcomeLearningService()
    now = datetime.now(timezone.utc)
    fresh_row = {"outcome_event": "recommendation_created", "created_at": (now - timedelta(hours=1)).isoformat()}
    stale_row = {"outcome_event": "recommendation_created", "created_at": (now - timedelta(hours=30)).isoformat()}
    service._fetch_events = AsyncMock(return_value=[fresh_row, stale_row])  # noqa: SLF001

    recent = await service.fetch_recent_events("org-1", since_hours=24)

    assert recent == [fresh_row]


@pytest.mark.asyncio
async def test_fetch_recent_events_skips_rows_with_missing_or_unparseable_timestamps():
    service = OutcomeLearningService()
    rows = [
        {"outcome_event": "x", "created_at": None},
        {"outcome_event": "y", "created_at": "not-a-timestamp"},
        {"outcome_event": "z"},
    ]
    service._fetch_events = AsyncMock(return_value=rows)  # noqa: SLF001

    recent = await service.fetch_recent_events("org-1", since_hours=24)

    assert recent == []


@pytest.mark.asyncio
async def test_fetch_recent_events_returns_empty_when_no_real_data_exists():
    """Honesty check: an org with no rows at all gets an empty list, never a fabricated one."""
    service = OutcomeLearningService()
    service._fetch_events = AsyncMock(return_value=[])  # noqa: SLF001

    recent = await service.fetch_recent_events("org-empty", since_hours=24)

    assert recent == []

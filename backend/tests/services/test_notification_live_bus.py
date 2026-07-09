"""Tests for live notification bus."""
from __future__ import annotations

import asyncio

import pytest

from app.services.notification_live_bus import publish, reset_subscribers_for_tests, subscribe, unsubscribe


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_subscribers_for_tests()
    yield
    reset_subscribers_for_tests()


@pytest.mark.asyncio
async def test_publish_delivers_to_subscriber():
    queue = subscribe("org-1", "user-1")
    delivered = publish(
        "org-1",
        "user-1",
        {"id": "notif-1", "title": "Task completed", "body": "Done"},
    )
    assert delivered == 1
    payload = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert payload["id"] == "notif-1"
    unsubscribe("org-1", "user-1", queue)

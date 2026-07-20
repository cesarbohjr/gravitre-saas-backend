"""Outcome event bus: publish is received by a live subscriber."""
from __future__ import annotations

from app.services.outcome_event_bus import (
    publish_outcome,
    reset_outcome_subscribers_for_tests,
    subscribe_outcomes,
    unsubscribe_outcomes,
)


def test_publish_delivers_to_subscriber() -> None:
    reset_outcome_subscribers_for_tests()
    org_id = "org-stream-test"
    queue = subscribe_outcomes(org_id)
    try:
        payload = {
            "schema_version": "1.0.0",
            "run_id": "run-1",
            "status": "failed",
            "source": "assignment",
        }
        delivered = publish_outcome(org_id, payload)
        assert delivered == 1
        received = queue.get_nowait()
        assert received["run_id"] == "run-1"
        assert received["schema_version"] == "1.0.0"
        assert received["status"] == "failed"
    finally:
        unsubscribe_outcomes(org_id, queue)
        reset_outcome_subscribers_for_tests()

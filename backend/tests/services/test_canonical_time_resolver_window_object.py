"""A proof's time window may already be a TimeWindow, not a dict."""
from __future__ import annotations

from datetime import date

from app.services.canonical_time_resolver import TimeWindow, time_window_from_mapping


def test_time_window_object_is_returned_as_is() -> None:
    window = time_window_from_mapping({"start": "2026-10-01", "end": "2026-10-07"})
    assert window is not None
    assert window.start == date(2026, 10, 1)
    assert time_window_from_mapping(window) is window
    assert isinstance(window, TimeWindow)

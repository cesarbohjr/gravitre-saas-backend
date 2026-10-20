"""All Stripe period queries must include every instant of the final UTC date."""
from datetime import date

from app.billing.stripe_research_lookup_metering import _month_bounds as research_bounds
from app.billing.stripe_voice_minutes_metering import _month_bounds as voice_bounds


def test_meter_windows_include_last_day_of_month():
    for bounds in (research_bounds, voice_bounds):
        start, end = bounds(date(2026, 10, 1), date(2026, 10, 31))
        assert start == "2026-10-01T00:00:00+00:00"
        assert end == "2026-11-01T00:00:00+00:00"


def test_meter_windows_handle_leap_day_and_year_rollover():
    for bounds in (research_bounds, voice_bounds):
        assert bounds(date(2028, 2, 1), date(2028, 2, 29))[1] == "2028-03-01T00:00:00+00:00"
        assert bounds(date(2026, 12, 1), date(2026, 12, 31))[1] == "2027-01-01T00:00:00+00:00"

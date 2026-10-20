from datetime import date

import pytest

from app.billing.stripe_meter_intents import (
    meter_event_identifier,
    new_overage_delta,
    ordered_event_deltas,
)


def test_identifier_is_stable_and_scoped_to_source_event():
    base = dict(org_id="org-1", environment="production",
                metric_type="ai_credits", period_start=date(2026, 10, 1))
    a = meter_event_identifier(**base, source_event_id="call-1")
    assert a == meter_event_identifier(**base, source_event_id="call-1")
    assert a != meter_event_identifier(**base, source_event_id="call-2")
    assert a != meter_event_identifier(**{**base, "org_id": "org-2"}, source_event_id="call-1")
    assert a != meter_event_identifier(**{**base, "environment": "staging"}, source_event_id="call-1")


def test_only_newly_excess_usage_is_charged():
    assert new_overage_delta(total_before=8, total_after=13, included=10) == 3
    assert new_overage_delta(total_before=13, total_after=18, included=10) == 5
    assert new_overage_delta(total_before=0, total_after=8, included=10) == 0


def test_ordered_deltas_never_rebill_allowance_when_next_batch_arrives():
    first = ordered_event_deltas([("a", 8), ("b", 5)], included=10)
    second = ordered_event_deltas([("a", 8), ("b", 5), ("c", 5)], included=10)
    assert first == [("a", 0), ("b", 3)]
    assert second[:2] == first
    assert second[-1] == ("c", 5)


@pytest.mark.parametrize("values", [[("same", 2), ("same", 1)], [("a", -1)]])
def test_duplicate_or_invalid_source_events_fail_closed(values):
    with pytest.raises(ValueError):
        ordered_event_deltas(values, included=3)

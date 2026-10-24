"""Voice usage queries must not silently report success on ledger failure."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from app.billing.stripe_voice_minutes_metering import report_voice_minutes_overage_to_stripe


class BrokenLedger:
    def table(self, name):
        assert name == "usage_records"
        raise RuntimeError("usage ledger unavailable")


def test_voice_meter_fails_closed_when_usage_read_is_unavailable():
    settings = SimpleNamespace(stripe_meter_outbox_enabled=False)
    with patch("app.billing.stripe_voice_minutes_metering.stripe.billing.MeterEvent.create") as send:
        result = report_voice_minutes_overage_to_stripe(
            "org-one", date(2026, 10, 1), date(2026, 10, 31),
            settings, client=BrokenLedger(),
        )
    assert result["error"] == "usage_query_failed"
    assert result["reported"] is False
    assert result["unreported_rows"] == 0
    send.assert_not_called()

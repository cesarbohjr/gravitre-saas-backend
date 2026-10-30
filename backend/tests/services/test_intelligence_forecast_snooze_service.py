from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.intelligence_forecast_snooze_service import (
    SNOOZE_KEY,
    SnoozeInputError,
    active_snoozes,
    list_snoozes,
    snooze_forecast,
    unsnooze_forecast,
)

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


class FakeOrgs:
    def __init__(self, settings: dict):
        self.settings = settings
        self.client = MagicMock()
        self.client.table.side_effect = self._table

    def _table(self, _name):
        t = MagicMock()
        t.select.return_value.eq.return_value.limit.return_value.execute.side_effect = (
            lambda: MagicMock(data=[{"settings": dict(self.settings)}])
        )

        def update(payload):
            self.settings = payload["settings"]
            return MagicMock()

        t.update.side_effect = update
        return t


def test_snooze_hides_a_forecast_until_the_date_and_keeps_other_settings():
    orgs = FakeOrgs({"branding": {"name": "Acme"}})
    with patch("app.workflows.audit.write_audit_event") as audit:
        out = snooze_forecast(
            orgs.client, "org-1", key="alert:a1", title="HubSpot sign-in needed", days=7, user_id="u1", user_name="Dana", now=NOW
        )
    assert out["until"] == (NOW + timedelta(days=7)).isoformat()
    assert orgs.settings["branding"] == {"name": "Acme"}
    assert list_snoozes(orgs.client, "org-1", now=NOW)[0]["key"] == "alert:a1"
    assert list_snoozes(orgs.client, "org-1", now=NOW + timedelta(days=8)) == []
    audit.assert_called_once()


def test_expired_snoozes_are_dropped_and_undo_brings_it_back():
    orgs = FakeOrgs({SNOOZE_KEY: {"old": {"until": (NOW - timedelta(days=1)).isoformat()}}})
    with patch("app.workflows.audit.write_audit_event"):
        snooze_forecast(orgs.client, "org-1", key="p:1", title="", days=1, user_id="u", user_name="", now=NOW)
        assert set(orgs.settings[SNOOZE_KEY]) == {"p:1"}
        assert unsnooze_forecast(orgs.client, "org-1", key="p:1", user_id="u", now=NOW) is True
        assert unsnooze_forecast(orgs.client, "org-1", key="p:1", user_id="u", now=NOW) is False
    assert active_snoozes(orgs.settings, NOW) == {}


def test_rejects_lengths_the_page_does_not_offer_and_empty_keys():
    orgs = FakeOrgs({})
    with pytest.raises(SnoozeInputError):
        snooze_forecast(orgs.client, "org-1", key="k", title="", days=3, user_id="u", user_name="", now=NOW)
    with pytest.raises(SnoozeInputError):
        snooze_forecast(orgs.client, "org-1", key="  ", title="", days=7, user_id="u", user_name="", now=NOW)

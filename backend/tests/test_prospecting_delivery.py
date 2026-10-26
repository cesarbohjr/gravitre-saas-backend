import pytest
from unittest.mock import MagicMock
from app.plays.prospecting_delivery import record_delivery_event

def test_unverified_event_must_not_query_database():
    client=MagicMock()
    with pytest.raises(PermissionError):
        record_delivery_event(client,org_id="a",provider="smartlead",event_id="ev",
            event_type="unsubscribed",provider_lead_id="l",source_verified=False)
    client.table.assert_not_called()

def test_unknown_event_type_fails_closed():
    with pytest.raises(ValueError):
        record_delivery_event(MagicMock(),org_id="a",provider="smartlead",event_id="ev",
            event_type="unsubscribe_me_now",provider_lead_id="l",source_verified=True)

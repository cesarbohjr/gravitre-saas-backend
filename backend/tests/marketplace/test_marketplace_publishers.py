"""MKT-AUDIT-11.1: Creator publisher onboarding."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.publishers import (
    MarketplacePublisherError,
    assert_org_can_publish_publicly,
    get_org_publisher_profile,
    onboard_org_publisher,
)

ORG_ID = "org-11111111-1111-1111-1111-111111111111"


def _table(*, data=None):
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.neq.return_value = mock
    mock.limit.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.execute.return_value = MagicMock(data=data or [])
    return mock


@patch("app.marketplace.publishers.write_audit_event")
def test_onboard_org_publisher_updates_existing(mock_audit):
    existing = _table(
        data=[
            {
                "id": "pub-1",
                "slug": "org-11111111",
                "org_id": ORG_ID,
                "public_publishing_enabled": False,
                "onboarded_at": None,
            }
        ]
    )
    refreshed = _table(
        data=[
            {
                "id": "pub-1",
                "slug": "acme-creators",
                "display_name": "Acme Creators",
                "org_id": ORG_ID,
                "public_publishing_enabled": True,
                "verified": False,
                "status": "active",
            }
        ]
    )
    client = MagicMock()
    call_count = {"n": 0}

    def table(name):
        if name != "marketplace_publishers":
            return MagicMock()
        call_count["n"] += 1
        if call_count["n"] == 1:
            return existing
        if call_count["n"] == 2:
            taken = _table(data=[])
            return taken
        return refreshed

    client.table.side_effect = table
    result = onboard_org_publisher(
        client,
        ORG_ID,
        actor_id="admin-1",
        display_name="Acme Creators",
        slug="acme-creators",
    )
    assert result["onboarded"] is True
    assert result["publisher"]["publicPublishingEnabled"] is True
    mock_audit.assert_called_once()


def test_assert_org_can_publish_publicly_requires_onboarding():
    client = MagicMock()
    client.table.return_value = _table(data=[])
    with pytest.raises(MarketplacePublisherError) as exc:
        assert_org_can_publish_publicly(client, ORG_ID)
    assert exc.value.code == "FORBIDDEN"


def test_get_org_publisher_profile_none():
    client = MagicMock()
    client.table.return_value = _table(data=[])
    assert get_org_publisher_profile(client, ORG_ID) is None

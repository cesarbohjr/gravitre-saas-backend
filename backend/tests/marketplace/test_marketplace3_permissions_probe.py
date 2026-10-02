from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.marketplace3.permissions_probe import (
    probe_outcome_pack_permissions,
)


ORG_ID = "11111111-1111-1111-1111-111111111111"
ASSET_ID = "22222222-2222-2222-2222-222222222222"


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _AsyncClient:
    responses = []

    def __init__(self, *args, **kwargs):
        self._responses = list(type(self).responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        return self._responses.pop(0)


def _query(data):
    q = MagicMock()
    q.select.return_value = q
    q.eq.return_value = q
    q.neq.return_value = q
    q.limit.return_value = q
    q.execute.return_value = MagicMock(data=data)
    return q


@pytest.mark.asyncio
async def test_permission_probe_requires_own_visibility_and_foreign_isolation():
    own = _query(
        [
            {
                "id": "own-play-install",
                "org_id": ORG_ID,
                "configuration": {"marketplaceAssetId": ASSET_ID},
            }
        ]
    )
    foreign = _query(
        [{"id": "foreign-play-install", "org_id": "99999999-9999-9999-9999-999999999999"}]
    )
    service = MagicMock()
    service.table.side_effect = [own, foreign]

    settings = MagicMock()
    settings.supabase_anon_key = "anon"
    settings.supabase_url_stripped = "https://example.supabase.co"

    _AsyncClient.responses = [
        _Response([{"id": "own-play-install", "org_id": ORG_ID}]),
        _Response([]),
    ]
    with patch(
        "app.marketplace.marketplace3.permissions_probe.httpx.AsyncClient",
        _AsyncClient,
    ):
        result = await probe_outcome_pack_permissions(
            service,
            settings,
            org_id=ORG_ID,
            asset_id=ASSET_ID,
            access_token="real-user-token",
        )

    assert result["passed"] is True
    assert result["ownVisible"] is True
    assert result["foreignHidden"] is True


@pytest.mark.asyncio
async def test_permission_probe_fails_closed_without_foreign_control_row():
    own = _query(
        [
            {
                "id": "own-play-install",
                "org_id": ORG_ID,
                "configuration": {"marketplaceAssetId": ASSET_ID},
            }
        ]
    )
    foreign = _query([])
    service = MagicMock()
    service.table.side_effect = [own, foreign]

    result = await probe_outcome_pack_permissions(
        service,
        MagicMock(),
        org_id=ORG_ID,
        asset_id=ASSET_ID,
        access_token="real-user-token",
    )

    assert result["passed"] is False
    assert result["reason"] == "foreign_control_row_unavailable"

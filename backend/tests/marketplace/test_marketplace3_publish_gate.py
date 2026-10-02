from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.publish import (
    MarketplacePublishError,
    _assert_outcome_pack_certification_current,
    approve_asset_for_internal_publish,
    approve_asset_for_public_publish,
)


ORG_ID = "11111111-1111-1111-1111-111111111111"
ASSET_ID = "22222222-2222-2222-2222-222222222222"


def _asset(*, scope: str = "internal") -> dict:
    return {
        "id": ASSET_ID,
        "org_id": ORG_ID,
        "slug": "msp-service-desk-3",
        "title": "MSP Service Desk 3.0",
        "asset_type": "outcome_pack",
        "status": "pending_review",
        "review_scope": scope,
        "visibility": "private",
        "config": {"marketplace_version": "3.0"},
        "required_connectors": [],
        "required_permissions": [],
        "install_variables": [],
        "current_version": 1,
    }


def _table():
    table = MagicMock()
    table.update.return_value = table
    table.insert.return_value = table
    table.eq.return_value = table
    table.execute.return_value = MagicMock(data=[])
    return table


@patch("app.marketplace.publish.assert_outcome_pack_publish_ready")
def test_outcome_pack_publish_helper_delegates_to_digest_bound_certification(mock_assert) -> None:
    mock_assert.return_value = {"level": "production_verified", "publishReady": True}
    asset = _asset()
    result = _assert_outcome_pack_certification_current(
        MagicMock(),
        asset,
        validated_config={"marketplace_version": "3.0", "plays": []},
    )
    assert result["publishReady"] is True
    mock_assert.assert_called_once()
    kwargs = mock_assert.call_args.kwargs
    assert kwargs["org_id"] == ORG_ID
    assert kwargs["asset_id"] == ASSET_ID


@patch("app.marketplace.publish._snapshot_version")
@patch("app.marketplace.publish._assert_outcome_pack_certification_current")
@patch("app.marketplace.publish.validate_asset_payload")
@patch("app.marketplace.publish._fetch_asset")
def test_internal_approval_cannot_bypass_outcome_pack_certification(
    mock_fetch,
    mock_validate,
    mock_certification,
    mock_snapshot,
) -> None:
    mock_fetch.return_value = _asset(scope="internal")
    mock_validate.return_value = {
        "config": {"marketplace_version": "3.0"},
        "required_connectors": [],
        "install_variables": [],
    }
    mock_certification.side_effect = MarketplacePublishError(
        "Outcome Pack has not reached Production Verified certification.",
        code="OUTCOME_PACK_CERTIFICATION_REQUIRED",
    )

    with pytest.raises(MarketplacePublishError) as exc:
        approve_asset_for_internal_publish(
            MagicMock(),
            ORG_ID,
            ASSET_ID,
            actor_id="admin-1",
        )

    assert exc.value.code == "OUTCOME_PACK_CERTIFICATION_REQUIRED"
    mock_snapshot.assert_not_called()


@patch("app.marketplace.publish._snapshot_version")
@patch("app.marketplace.publish._assert_outcome_pack_certification_current")
@patch("app.marketplace.publish.validate_asset_payload")
@patch("app.marketplace.publish._fetch_asset")
def test_public_approval_cannot_bypass_outcome_pack_certification(
    mock_fetch,
    mock_validate,
    mock_certification,
    mock_snapshot,
) -> None:
    mock_fetch.return_value = _asset(scope="public")
    mock_validate.return_value = {
        "config": {"marketplace_version": "3.0"},
        "required_connectors": [],
        "install_variables": [],
    }
    mock_certification.side_effect = MarketplacePublishError(
        "Outcome Pack certification is stale or incomplete.",
        code="OUTCOME_PACK_CERTIFICATION_REQUIRED",
    )

    with pytest.raises(MarketplacePublishError) as exc:
        approve_asset_for_public_publish(
            MagicMock(),
            ASSET_ID,
            actor_id="platform-admin-1",
            org_id=ORG_ID,
        )

    assert exc.value.code == "OUTCOME_PACK_CERTIFICATION_REQUIRED"
    mock_snapshot.assert_not_called()

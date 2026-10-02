import pytest

from app.marketplace.crud import _ASSET_TYPES
from app.marketplace.marketplace3.security_operations import (
    build_security_operations_outcome_pack_config,
)
from app.marketplace.publish import (
    MarketplacePublishError,
    _assert_outcome_pack_publish_ready,
)


def test_marketplace3_asset_types_are_authorable_through_org_crud() -> None:
    assert {
        "play",
        "dataset_pack",
        "dashboard_pack",
        "outcome_pack",
    } <= _ASSET_TYPES


def test_uncertified_outcome_pack_cannot_publish() -> None:
    config = build_security_operations_outcome_pack_config()

    with pytest.raises(MarketplacePublishError) as exc:
        _assert_outcome_pack_publish_ready("outcome_pack", config)

    assert exc.value.code == "OUTCOME_PACK_NOT_CERTIFIED"


def test_non_outcome_assets_do_not_require_outcome_certification() -> None:
    _assert_outcome_pack_publish_ready("workflow", {})

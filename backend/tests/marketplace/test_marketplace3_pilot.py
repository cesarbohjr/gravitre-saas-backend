from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.marketplace.seed_catalog import catalog_assets_by_slug
from app.marketplace.service import MarketplaceError, _assert_asset_installable, _outcome_skill_asset, install_asset
from app.marketplace.seed_service import _asset_row
from app.marketplace.schemas import validate_asset_payload


def _pack():
    asset = catalog_assets_by_slug()["msp-service-desk-3"]
    validated = validate_asset_payload(asset_type=asset.asset_type, config=asset.config, publish=False)
    return {"id": "asset-1", **_asset_row("publisher-1", asset, validated=validated)}


def test_regular_install_still_rejects_governed_draft():
    with pytest.raises(MarketplaceError) as error:
        _assert_asset_installable(_pack())
    assert error.value.code == "NOT_PUBLISHED"
    _assert_asset_installable(_pack(), draft_pilot=True)


@pytest.mark.parametrize("field,value", [("status", "published"), ("visibility", "public"), ("asset_type", "ai_agent"), ("org_id", "other-org"), ("tags", [])])
def test_pilot_rejects_other_asset_scopes(field, value):
    asset = _pack()
    asset[field] = value
    with pytest.raises(MarketplaceError) as error:
        _assert_asset_installable(asset, draft_pilot=True)
    assert error.value.code == "PILOT_NOT_ALLOWED"


def test_pilot_requires_passing_governed_contracts():
    asset = _pack()
    asset["config"]["skill_bindings"] = {}
    with pytest.raises(MarketplaceError) as error:
        _assert_asset_installable(asset, draft_pilot=True)
    assert error.value.code == "PILOT_NOT_READY"


def test_pilot_preserves_connector_gate_and_cannot_force(monkeypatch):
    asset = _pack()
    monkeypatch.setattr("app.marketplace.service.fetch_marketplace_asset", lambda *_a: asset)
    entitlement = MagicMock()
    monkeypatch.setattr("app.marketplace.entitlements.assert_install_entitlement", entitlement)
    monkeypatch.setattr("app.marketplace.service.validate_connectors_for_asset", lambda *_a, **_k: {"can_install": False, "checklist": [], "blockers": [{"connector": "freshservice"}]})
    materialize = MagicMock()
    monkeypatch.setattr("app.marketplace.service._install_outcome_pack", materialize)
    with pytest.raises(MarketplaceError) as error:
        install_asset(MagicMock(), "org-1", asset["id"], actor_id="platform-1", _draft_pilot=True)
    assert error.value.code == "CONNECTORS_NOT_READY"
    with pytest.raises(MarketplaceError) as error:
        install_asset(MagicMock(), "org-1", asset["id"], actor_id="platform-1", _draft_pilot=True, force=True)
    assert error.value.code == "PILOT_NOT_ALLOWED"
    entitlement.assert_not_called()
    materialize.assert_not_called()
    assert asset["status"] == "draft"


@pytest.mark.parametrize("change", [None, "unlinked", "publisher", "scope", "archived", "no_permission"])
def test_only_linked_internal_bundle_skills_are_available_to_pilot(change):
    parent = _pack()
    skill = {"id": "skill-1", "status": "draft", "visibility": "internal", "org_id": None,
             "publisher_id": parent["publisher_id"], "tags": ["marketplace-3"]}
    if change == "publisher":
        skill["publisher_id"] = "other"
    elif change == "scope":
        skill["visibility"] = "private"
    elif change == "archived":
        skill["status"] = "archived"
    assets = MagicMock()
    assets.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = SimpleNamespace(data=[skill])
    links = MagicMock()
    links.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = SimpleNamespace(data=[] if change == "unlinked" else [{"id": "link-1"}])
    client = MagicMock()
    client.table.side_effect = lambda name: assets if name == "marketplace_assets" else links
    if change is None:
        assert _outcome_skill_asset(client, parent, "skill-ref", allow_draft=True) == skill
        assert skill["status"] == "draft"
    else:
        with pytest.raises(MarketplaceError) as error:
            _outcome_skill_asset(client, parent, "skill-ref", allow_draft=change != "no_permission")
        assert error.value.code == "OUTCOME_PACK_SKILL_MISSING"


def test_malformed_pilot_config_reports_readiness_failure():
    asset = _pack()
    asset["config"] = {}
    with pytest.raises(MarketplaceError) as error:
        _assert_asset_installable(asset, draft_pilot=True)
    assert error.value.code == "PILOT_NOT_READY"

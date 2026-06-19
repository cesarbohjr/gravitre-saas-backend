"""MKT-AUDIT-5.5: Knowledge pack install coverage."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.marketplace.service import install_asset

ASSET_ID = "33333333-3333-3333-3333-333333333333"


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.limit.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.upsert.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])
    return mock


def _knowledge_pack_asset() -> dict:
    return {
        "id": ASSET_ID,
        "slug": "marketing-operations-knowledge",
        "asset_type": "knowledge_pack",
        "status": "published",
        "visibility": "public",
        "current_version": 1,
        "install_count": 0,
        "required_connectors": [],
        "install_variables": [],
        "config": {
            "documents": [
                {"seed_label": "rag:brand-voice", "title": "Brand Voice Guide", "type": "manual", "metadata": {}},
                {"seed_label": "rag:campaigns", "title": "Campaign Playbooks", "type": "manual", "metadata": {}},
            ]
        },
    }


@patch("app.marketplace.service.write_audit_event")
@patch("app.marketplace.service.increment_marketplace_counter")
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": None, "workflows_limit": None})
def test_install_creates_rag_source(mock_plan, mock_counter, mock_audit):
    asset = _knowledge_pack_asset()
    assets = _table([asset])
    installs = _table([])
    rag = _table([])
    rag.upsert.return_value = rag

    client = MagicMock()
    client.table.side_effect = lambda name: {
        "marketplace_assets": assets,
        "marketplace_installs": installs,
        "rag_sources": rag,
    }.get(name, _table([]))

    result = install_asset(client, "org-1", ASSET_ID, actor_id="user-1")
    assert result["installed"] is True
    assert result["entities"]["entityType"] == "knowledge_pack"
    assert len(result["entities"]["ragSourceIds"]) == 2
    rag.upsert.assert_called_once()


@patch("app.marketplace.service.write_audit_event")
@patch("app.marketplace.service.increment_marketplace_counter")
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": None, "workflows_limit": None})
def test_knowledge_pack_install_does_not_require_agent_quota(mock_plan, mock_counter, mock_audit):
    asset = _knowledge_pack_asset()
    assets = _table([asset])
    installs = _table([])
    rag = _table([])
    rag.upsert.return_value = rag

    client = MagicMock()
    client.table.side_effect = lambda name: {
        "marketplace_assets": assets,
        "marketplace_installs": installs,
        "rag_sources": rag,
    }.get(name, _table([]))

    result = install_asset(client, "org-1", ASSET_ID, actor_id="user-1")
    assert result["installed"] is True
    mock_plan.assert_called_once()
